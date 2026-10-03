"""
Master pool service.

The pool is a separate contact list owned by the master organization.
Contacts enter it only when an associate explicitly grants permission
via a recorded PoolPermission. Contacts leave when permission is
revoked or the customer opts out.
"""
from datetime import datetime

from app.extensions import db
from app.models import (Organization, Contact, OptOut,
                        PoolPermission, PoolContact)
from app.services.audit import log as audit


AGREEMENT_VERSION = 'v1'
AGREEMENT_TEXT = """
By enabling contact sharing, I confirm that:

1. I am the owner or authorised administrator of the organization
   granting this permission.

2. I have a lawful basis for the personal data in this list, and I
   have informed my customers that their contact information may be
   used by Roman SMS Ltd for platform-level communications and
   promotions.

3. I understand that Roman SMS Ltd will receive a copy of my
   organization's active (non opted-out) contacts, including name,
   phone number, and district.

4. I understand that Roman SMS Ltd may send messages to those contacts
   under its own brand.

5. I may revoke this permission at any time. On revocation, Roman SMS
   Ltd will remove all contacts contributed by my organization from
   the master pool, except where those contacts were also contributed
   by another organization that has granted the same permission.

6. Customers may opt out of Roman SMS communications at any time, and
   this will be honoured platform-wide.
"""


class PoolError(Exception):
    pass


# --------------------------------------------------------------------------
# Permission
# --------------------------------------------------------------------------

def get_active_permission(org):
    return (PoolPermission.query
            .filter_by(org_id=org.id, status='active')
            .order_by(PoolPermission.id.desc())
            .first())


def permission_history(org):
    return (PoolPermission.query
            .filter_by(org_id=org.id)
            .order_by(PoolPermission.id.desc())
            .all())


def grant_permission(org, user, *, note=None):
    """Record a grant and copy eligible contacts into the pool."""
    if get_active_permission(org):
        raise PoolError('This organization already has an active grant.')

    permission = PoolPermission(
        org_id=org.id,
        granted_by=user.id,
        agreement_version=AGREEMENT_VERSION,
        agreement_text=AGREEMENT_TEXT.strip(),
        note=(note or '').strip() or None,
        status='active',
    )
    db.session.add(permission)
    db.session.flush()

    copied = _copy_contacts_into_pool(org)
    db.session.commit()

    audit('pool_permission_grant',
          f'org={org.slug} copied={copied} version={AGREEMENT_VERSION}',
          org_id=org.id, actor_id=user.id)
    return permission, copied


def revoke_permission(org, user, *, note=None):
    """Revoke the grant and remove the organization's rows from the pool."""
    permission = get_active_permission(org)
    if not permission:
        raise PoolError('No active grant to revoke.')

    removed = (PoolContact.query
               .filter_by(source_org_id=org.id)
               .delete(synchronize_session=False))

    permission.status = 'revoked'
    permission.revoked_by = user.id
    permission.revoked_at = datetime.utcnow()
    if note:
        permission.note = (permission.note or '') + f' | revoke: {note}'

    db.session.commit()
    audit('pool_permission_revoke',
          f'org={org.slug} removed={removed}',
          org_id=org.id, actor_id=user.id)
    return permission, removed


# --------------------------------------------------------------------------
# Copy / sync
# --------------------------------------------------------------------------

def _copy_contacts_into_pool(org):
    """
    Copy every active (not opted-out, not platform-opted-out) contact
    from org into the pool. Idempotent — uses upsert-style logic.
    Returns the number of new rows created.
    """
    blocked = {r[0] for r in db.session.query(OptOut.phone).all()}

    existing_phones = {
        r[0] for r in db.session.query(PoolContact.phone)
        .filter_by(source_org_id=org.id).all()
    }

    candidates = (Contact.query
                  .filter_by(org_id=org.id, opted_out=False)
                  .all())

    added = 0
    for c in candidates:
        if c.phone in blocked:
            continue
        if c.phone in existing_phones:
            continue
        db.session.add(PoolContact(
            phone=c.phone,
            name=c.name,
            # Snapshot the group name. If the contact has no group this
            # is None, which is fine — most do not.
            group_name=(c.group.name if c.group else None),
            district_id=c.district_id,
            source_org_id=org.id,
            source_contact_id=c.id,
            opted_out=False,
        ))
        added += 1

    return added


def unique_recipients(*, district_id=None, source_org_id=None,
                      group_name=None):
    """
    Return a list of deduplicated PoolContact recipients for a campaign.

    Same phone shared from two orgs appears once. If one source has it
    opted-out, it is excluded globally.

    Filters (all optional, all AND-combined):
      district_id     — contacts in this district
      source_org_id   — contacts originally from this associate
      group_name      — contacts snapshotted with this group name
                        (case-insensitive exact match)
    """
    blocked = {r[0] for r in db.session.query(OptOut.phone).all()}

    q = PoolContact.query
    if district_id:
        q = q.filter_by(district_id=district_id)
    if source_org_id:
        q = q.filter_by(source_org_id=source_org_id)
    if group_name:
        q = q.filter(
            db.func.lower(PoolContact.group_name) == group_name.strip().lower()
        )

    seen = set()
    recipients = []
    for row in q.order_by(PoolContact.id.asc()).all():
        if row.phone in seen:
            continue
        if row.opted_out:
            continue
        if row.phone in blocked:
            continue
        seen.add(row.phone)
        recipients.append(row)
    return recipients


def list_pool_groups():
    """
    Return the distinct group names present in the pool, sorted.
    Excludes NULL and empty strings. Used to populate filter dropdowns.
    """
    rows = (db.session.query(PoolContact.group_name)
            .filter(PoolContact.group_name.isnot(None),
                    PoolContact.group_name != '',
                    PoolContact.opted_out.is_(False))
            .distinct()
            .order_by(PoolContact.group_name)
            .all())
    return [r[0] for r in rows if r[0]]


def resync_org(org):
    """Called after an import or bulk change while permission is active."""
    if not get_active_permission(org):
        return 0
    added = _copy_contacts_into_pool(org)
    db.session.commit()
    return added


def propagate_opt_out(phone):
    """
    Called whenever a phone is added to the platform-wide OptOut table.
    Marks every pool row with this phone as opted out.
    """
    n = (PoolContact.query
         .filter_by(phone=phone, opted_out=False)
         .update({'opted_out': True}, synchronize_session=False))
    db.session.commit()
    return n


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------

def pool_stats():
    total = PoolContact.query.filter_by(opted_out=False).count()

    by_district = (db.session.query(
                        PoolContact.district_id,
                        db.func.count(PoolContact.id))
                   .filter(PoolContact.opted_out.is_(False))
                   .group_by(PoolContact.district_id).all())

    by_source = (db.session.query(
                     Organization.name,
                     db.func.count(PoolContact.id))
                 .join(Organization,
                       Organization.id == PoolContact.source_org_id)
                 .filter(PoolContact.opted_out.is_(False))
                 .group_by(Organization.id).all())

    by_group = (db.session.query(
                    PoolContact.group_name,
                    db.func.count(PoolContact.id))
                .filter(PoolContact.opted_out.is_(False),
                        PoolContact.group_name.isnot(None),
                        PoolContact.group_name != '')
                .group_by(PoolContact.group_name)
                .order_by(db.func.count(PoolContact.id).desc())
                .all())

    return {
        'total': total,
        'by_district_id': dict(by_district),
        'by_source': by_source,
        'by_group': by_group,
    }


def list_pool_contacts(*, district_id=None, source_org_id=None,
                       group_name=None, limit=500):
    q = PoolContact.query.filter_by(opted_out=False)
    if district_id:
        q = q.filter_by(district_id=district_id)
    if source_org_id:
        q = q.filter_by(source_org_id=source_org_id)
    if group_name:
        q = q.filter(
            db.func.lower(PoolContact.group_name) == group_name.strip().lower()
        )
    return q.order_by(PoolContact.id.desc()).limit(limit).all()