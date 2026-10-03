import csv
import io
from app.extensions import db
from app.models import Contact, OptOut
from app.services.phones import normalize_ug
from app.services.entitlements import check_contact_limit, EntitlementError
from app.services.audit import log as audit
from app.services import groups as groups_svc


class ContactError(Exception):
    pass


def add_contact(org, *, phone, name=None, group=None, group_id=None,
                district_id=None):
    """
    Create a contact.

    name and district_id are both optional. Passing None stores a NULL,
    which is what we want for "no name" and "no district". Passing an
    empty string is treated as None too.
    """
    normalized = normalize_ug(phone)
    if not normalized:
        raise ContactError('Invalid Ugandan phone number.')

    existing = Contact.query.filter_by(org_id=org.id, phone=normalized).first()
    if existing:
        raise ContactError('Contact already exists.')

    try:
        check_contact_limit(org, 1)
    except EntitlementError as e:
        raise ContactError(str(e))

    resolved_group_id = None
    if group_id:
        g = groups_svc.get(org, group_id)
        if not g:
            raise ContactError('Group not found.')
        resolved_group_id = g.id
    elif group:
        g, _ = groups_svc.find_or_create(org, group)
        if g:
            resolved_group_id = g.id

    # Clean up optional fields: empty string -> None
    clean_name = (name or '').strip() or None
    clean_district_id = district_id or None

    contact = Contact(
        org_id=org.id, phone=normalized,
        name=clean_name,
        group_id=resolved_group_id,
        district_id=clean_district_id,
    )
    db.session.add(contact)
    db.session.commit()
    audit('contact_create', normalized)
    return contact


def update_contact(org, contact_id, *, name=None, group_id=None,
                   clear_group=False, district_id=None,
                   clear_district=False):
    """
    Update a contact.

    name: pass a string to update, or '' / None to clear it.
    district_id: pass an id to set, or use clear_district=True to null it.
    """
    contact = Contact.query.filter_by(id=contact_id, org_id=org.id).first()
    if not contact:
        raise ContactError('Contact not found.')

    if name is not None:
        # Empty or whitespace-only becomes None, not ''
        contact.name = name.strip() or None

    if clear_group:
        contact.group_id = None
    elif group_id is not None:
        g = groups_svc.get(org, group_id)
        if not g:
            raise ContactError('Group not found.')
        contact.group_id = g.id

    if clear_district:
        contact.district_id = None
    elif district_id is not None:
        contact.district_id = district_id

    db.session.commit()
    return contact


def delete_contact(org, contact_id):
    contact = Contact.query.filter_by(id=contact_id, org_id=org.id).first()
    if not contact:
        raise ContactError('Contact not found.')
    db.session.delete(contact)
    db.session.commit()
    audit('contact_delete', contact.phone)


def mark_opted_out(org, contact_id, reason='associate_manual'):
    """Mark a contact opted out and propagate to the master pool."""
    from app.services import pool as pool_svc

    contact = Contact.query.filter_by(id=contact_id, org_id=org.id).first()
    if not contact:
        raise ContactError('Contact not found.')

    contact.opted_out = True
    if not OptOut.query.filter_by(phone=contact.phone).first():
        db.session.add(OptOut(phone=contact.phone, reason=reason))
        db.session.flush()
        pool_svc.propagate_opt_out(contact.phone)

    db.session.commit()
    audit('contact_optout', contact.phone)
    return contact


def import_csv(org, file_stream, *,
               default_group=None,
               default_district_id=None,
               on_duplicate='skip',
               filename=None,
               user_id=None):
    """
    Import contacts from a CSV and create a persistent report.

    Returns a ContactImport row. The caller should redirect to the
    report page rather than flash a summary.

    Duplicate handling:
      on_duplicate='skip'   — leave existing contact untouched
      on_duplicate='update' — update name/group/district from the file
    """
    from app.services import geo as geo_svc
    from app.services.phones import normalize_ug, describe
    from app.models import ContactImport, ContactImportIssue

    # --- Read file ---
    text = file_stream.read()
    file_size = len(text)
    if isinstance(text, bytes):
        # utf-8-sig strips the BOM Excel prepends.
        text = text.decode('utf-8-sig', errors='ignore')

    reader = csv.DictReader(io.StringIO(text))

    # Create the job record up front so we have an id to attach issues to.
    job = ContactImport(
        org_id=org.id,
        user_id=user_id,
        filename=(filename or '')[:255] or None,
        file_size=file_size,
        on_duplicate=on_duplicate,
        default_group=(default_group or '')[:80] or None,
        default_district_id=default_district_id or None,
    )
    db.session.add(job)
    db.session.flush()

    if not reader.fieldnames:
        db.session.commit()
        return job

    # --- Locate the phone column ---
    lower_names = [(f or '').strip().lower() for f in reader.fieldnames]
    phone_columns = [
        'phone', 'number', 'mobile', 'msisdn',
        'phone_number', 'phone number',
        'mobile_number', 'mobile number',
        'telephone', 'tel', 'contact_phone',
    ]
    phone_key = None
    for candidate in phone_columns:
        if candidate in lower_names:
            phone_key = reader.fieldnames[lower_names.index(candidate)]
            break

    if phone_key is None:
        # Record the failure as a job-level note, not a per-row issue.
        job.invalid = 0
        db.session.commit()
        raise ContactError(
            'CSV is missing a phone number column. '
            'Accepted headers: ' + ', '.join(phone_columns) + '.'
        )

    # --- Load lookups once ---
    opt_outs = {r[0] for r in db.session.query(OptOut.phone).all()}
    existing_by_phone = {
        c.phone: c
        for c in Contact.query.filter_by(org_id=org.id).all()
    }

    # --- Defaults ---
    default_group_obj = None
    if default_group:
        default_group_obj, created = groups_svc.find_or_create(
            org, default_group)
        if created:
            job.groups_created = (job.groups_created or 0) + 1

    default_district_obj = None
    if default_district_id:
        default_district_obj = geo_svc.get(default_district_id)

    # --- Caches ---
    group_cache = {}
    district_cache = {}
    seen_in_file = set()

    # --- Process ---
    for row_num, raw_row in enumerate(reader, start=2):
        row = {(k or '').strip().lower(): v for k, v in raw_row.items()}

        raw_phone = (row.get(phone_key.lower()) or '').strip()
        canonical = normalize_ug(raw_phone)

        # Get name, group, district for storage and for the issue log.
        name = (row.get('name') or '').strip()
        group_name = (row.get('group') or '').strip()
        district_name = (row.get('district') or '').strip()

        # -- Invalid --
        if not canonical:
            _, reason = describe(raw_phone)
            job.invalid = (job.invalid or 0) + 1
            db.session.add(ContactImportIssue(
                import_id=job.id, row_num=row_num,
                status='invalid', reason=reason or 'invalid',
                raw_phone=raw_phone[:60],
                name=name[:120] or None,
                group_name=group_name[:80] or None,
                district_name=district_name[:80] or None,
            ))
            continue

        # -- Platform-wide opt-out --
        if canonical in opt_outs:
            job.skipped_opt_out = (job.skipped_opt_out or 0) + 1
            db.session.add(ContactImportIssue(
                import_id=job.id, row_num=row_num,
                status='opted_out',
                reason='On the platform-wide opt-out list',
                raw_phone=raw_phone[:60],
                canonical=canonical,
                name=name[:120] or None,
                group_name=group_name[:80] or None,
                district_name=district_name[:80] or None,
            ))
            continue

        # -- Duplicate within this file --
        if canonical in seen_in_file:
            job.skipped_in_file = (job.skipped_in_file or 0) + 1
            db.session.add(ContactImportIssue(
                import_id=job.id, row_num=row_num,
                status='duplicate_file',
                reason='Same number appears earlier in this file',
                raw_phone=raw_phone[:60],
                canonical=canonical,
                name=name[:120] or None,
                group_name=group_name[:80] or None,
                district_name=district_name[:80] or None,
            ))
            continue
        seen_in_file.add(canonical)

        # -- Resolve group --
        group_obj = default_group_obj
        if group_name:
            key = group_name.lower()
            if key in group_cache:
                group_obj = group_cache[key]
            else:
                g, created = groups_svc.find_or_create(org, group_name)
                if created:
                    job.groups_created = (job.groups_created or 0) + 1
                group_cache[key] = g
                group_obj = g

        # -- Resolve district (never auto-created) --
        district_obj = default_district_obj
        if district_name:
            key = district_name.lower()
            if key in district_cache:
                district_obj = district_cache[key]
            else:
                d = geo_svc.find_by_name(district_name)
                district_cache[key] = d
                district_obj = d
            if district_obj:
                job.districts_matched = (job.districts_matched or 0) + 1
            else:
                job.districts_unmatched = (
                    (job.districts_unmatched or 0) + 1)

        # -- Existing contact --
        existing = existing_by_phone.get(canonical)
        if existing:
            if on_duplicate == 'update':
                touched = False
                if name and name != (existing.name or ''):
                    existing.name = name
                    touched = True
                if group_obj and existing.group_id != group_obj.id:
                    existing.group_id = group_obj.id
                    touched = True
                if district_obj and existing.district_id != district_obj.id:
                    existing.district_id = district_obj.id
                    touched = True
                if touched:
                    job.updated = (job.updated or 0) + 1
                else:
                    job.skipped_duplicate = (
                        (job.skipped_duplicate or 0) + 1)
                    db.session.add(ContactImportIssue(
                        import_id=job.id, row_num=row_num,
                        status='duplicate_db',
                        reason='Already in your list, no changes',
                        raw_phone=raw_phone[:60],
                        canonical=canonical,
                        name=name[:120] or None,
                        group_name=group_name[:80] or None,
                        district_name=district_name[:80] or None,
                    ))
            else:
                job.skipped_duplicate = (
                    (job.skipped_duplicate or 0) + 1)
                db.session.add(ContactImportIssue(
                    import_id=job.id, row_num=row_num,
                    status='duplicate_db',
                    reason='Already in your list',
                    raw_phone=raw_phone[:60],
                    canonical=canonical,
                    name=name[:120] or None,
                    group_name=group_name[:80] or None,
                    district_name=district_name[:80] or None,
                ))
            continue

        # -- Plan cap (only when actually adding) --
        try:
            check_contact_limit(org, 1)
        except EntitlementError:
            job.cap_hit = True
            break

        # -- Insert --
        contact = Contact(
            org_id=org.id,
            phone=canonical,
            name=name,
            group_id=group_obj.id if group_obj else None,
            district_id=district_obj.id if district_obj else None,
        )
        db.session.add(contact)
        existing_by_phone[canonical] = contact
        job.added = (job.added or 0) + 1

    # Total rows counter
    job.total_rows = (
        (job.added or 0)
        + (job.updated or 0)
        + (job.skipped_duplicate or 0)
        + (job.skipped_in_file or 0)
        + (job.skipped_opt_out or 0)
        + (job.invalid or 0)
    )

    db.session.commit()

    audit('contact_import',
          f'job={job.id} file={job.filename or "-"} '
          f'added={job.added} updated={job.updated} '
          f'skip_db={job.skipped_duplicate} '
          f'skip_file={job.skipped_in_file} '
          f'opt_out={job.skipped_opt_out} '
          f'invalid={job.invalid} '
          f'cap_hit={job.cap_hit}')

    return job


def export_all(org):
    rows = (Contact.query
            .filter_by(org_id=org.id)
            .order_by(Contact.id)
            .all())
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['phone', 'name', 'group', 'district', 'opted_out'])
    for c in rows:
        w.writerow([c.phone, c.name or '',
                    c.group.name if c.group else '',
                    c.district.name if c.district else '',
                    'yes' if c.opted_out else 'no'])
    return buf.getvalue()


def all_groups(org):
    """Legacy helper. Returns group names only."""
    return groups_svc.list_names(org)