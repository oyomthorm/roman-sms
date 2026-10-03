from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, Response)
from flask_login import login_required, current_user

from app.extensions import db
from app.permissions import org_scoped
from app.models import Contact, OptOut
from app.services import contacts as svc
from app.services import groups as groups_svc
from app.services import geo as geo_svc

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, Response, abort)
from flask_login import login_required, current_user
from app.models import Contact, OptOut, ContactImport, ContactImportIssue


contacts_bp = Blueprint('contacts', __name__)


def _org():
    return current_user.organization


@contacts_bp.route('/')
@login_required
def index():
    org = _org()
    q = (request.args.get('q') or '').strip()
    group_id_raw = (request.args.get('group_id') or '').strip()
    district_id_raw = (request.args.get('district_id') or '').strip()
    group_id = int(group_id_raw) if group_id_raw.isdigit() else None
    district_id = int(district_id_raw) if district_id_raw.isdigit() else None

    query = org_scoped(Contact)
    if q:
        like = f'%{q}%'
        query = query.filter(db.or_(Contact.phone.ilike(like),
                                    Contact.name.ilike(like)))
    if group_id:
        query = query.filter_by(group_id=group_id)
    if district_id:
        query = query.filter_by(district_id=district_id)

    contacts = query.order_by(Contact.id.desc()).limit(500).all()
    groups = groups_svc.list_groups(org)
    districts_by_region = geo_svc.list_by_region()
    return render_template('contacts/list.html',
                           contacts=contacts, groups=groups,
                           districts_by_region=districts_by_region,
                           q=q, group_id=group_id,
                           district_id=district_id)


@contacts_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    org = _org()
    if request.method == 'POST':
        group_id_raw = request.form.get('group_id', '').strip()
        group_id = int(group_id_raw) if group_id_raw.isdigit() else None

        district_id_raw = request.form.get('district_id', '').strip()
        district_id = int(district_id_raw) if district_id_raw.isdigit() else None

        try:
            svc.add_contact(
                org,
                phone=request.form.get('phone', ''),
                name=request.form.get('name', ''),
                group=request.form.get('group_new', ''),
                group_id=group_id,
                district_id=district_id,
            )
        except svc.ContactError as e:
            flash(str(e), 'danger')
            return render_template('contacts/form.html',
                                   contact=None,
                                   groups=groups_svc.list_groups(org),
                                   districts_by_region=geo_svc.list_by_region())
        flash('Contact added.', 'success')
        return redirect(url_for('contacts.index'))

    return render_template('contacts/form.html',
                           contact=None,
                           groups=groups_svc.list_groups(org),
                           districts_by_region=geo_svc.list_by_region())


@contacts_bp.route('/<int:cid>/edit', methods=['GET', 'POST'])
@login_required
def edit(cid):
    org = _org()
    contact = org_scoped(Contact).filter_by(id=cid).first_or_404()
    if request.method == 'POST':
        group_id_raw = request.form.get('group_id', '').strip()
        group_id = int(group_id_raw) if group_id_raw.isdigit() else None
        clear_group = (group_id_raw == '')

        district_id_raw = request.form.get('district_id', '').strip()
        district_id = int(district_id_raw) if district_id_raw.isdigit() else None
        clear_district = (district_id_raw == '')

        try:
            svc.update_contact(org, cid,
                               name=request.form.get('name', ''),
                               group_id=group_id,
                               clear_group=clear_group,
                               district_id=district_id,
                               clear_district=clear_district)
        except svc.ContactError as e:
            flash(str(e), 'danger')
        else:
            flash('Contact updated.', 'success')
            return redirect(url_for('contacts.index'))

    return render_template('contacts/form.html',
                           contact=contact,
                           groups=groups_svc.list_groups(org),
                           districts_by_region=geo_svc.list_by_region())


@contacts_bp.route('/<int:cid>/delete', methods=['POST'])
@login_required
def delete(cid):
    try:
        svc.delete_contact(_org(), cid)
        flash('Contact deleted.', 'success')
    except svc.ContactError as e:
        flash(str(e), 'danger')
    return redirect(url_for('contacts.index'))


@contacts_bp.route('/<int:cid>/optout', methods=['POST'])
@login_required
def optout(cid):
    try:
        c = svc.mark_opted_out(_org(), cid)
        flash(f'{c.phone} opted out.', 'success')
    except svc.ContactError as e:
        flash(str(e), 'danger')
    return redirect(url_for('contacts.index'))


@contacts_bp.route('/import', methods=['GET'])
@login_required
def import_page():
    org = _org()

    # Phones that already exist for this org. Capped so the page stays fast.
    existing_phones = [
        row[0] for row in
        db.session.query(Contact.phone)
        .filter_by(org_id=org.id)
        .order_by(Contact.id.desc())
        .limit(5000)
        .all()
    ]

    # Platform-wide opt-outs. Also capped.
    opt_out_phones = [
        row[0] for row in
        db.session.query(OptOut.phone)
        .order_by(OptOut.id.desc())
        .limit(5000)
        .all()
    ]

    groups = groups_svc.list_groups(org)
    districts_by_region = geo_svc.list_by_region()
    return render_template(
        'contacts/import.html',
        existing_phones=existing_phones,
        opt_out_phones=opt_out_phones,
        groups=groups,
        districts_by_region=districts_by_region,
    )


@contacts_bp.route('/import', methods=['POST'])
@login_required
def import_csv():
    file = request.files.get('file')
    if not file or not file.filename:
        flash('No file uploaded.', 'danger')
        return redirect(url_for('contacts.import_page'))

    group_name = request.form.get('group', '').strip() or None
    district_id_raw = request.form.get('district_id', '').strip()
    district_id = int(district_id_raw) if district_id_raw.isdigit() else None

    on_duplicate = request.form.get('on_duplicate', 'skip').strip()
    if on_duplicate not in ('skip', 'update'):
        on_duplicate = 'skip'

    try:
        job = svc.import_csv(
            _org(), file.stream,
            default_group=group_name,
            default_district_id=district_id,
            on_duplicate=on_duplicate,
            filename=file.filename,
            user_id=current_user.id,
        )
    except svc.ContactError as e:
        flash(str(e), 'danger')
        return redirect(url_for('contacts.import_page'))

    return redirect(url_for('contacts.import_report', job_id=job.id))


@contacts_bp.route('/imports')
@login_required
def import_history():
    """List past imports for this org."""
    org = _org()
    jobs = (ContactImport.query
            .filter_by(org_id=org.id)
            .order_by(ContactImport.id.desc())
            .limit(100)
            .all())
    return render_template('contacts/import_history.html', jobs=jobs)


@contacts_bp.route('/imports/<int:job_id>')
@login_required
def import_report(job_id):
    """Full report for one import."""
    org = _org()
    job = ContactImport.query.filter_by(
        id=job_id, org_id=org.id).first_or_404()

    # Optional filter by status. Useful when there are hundreds of issues.
    status = (request.args.get('status') or '').strip()
    allowed = {'invalid', 'duplicate_db', 'duplicate_file', 'opted_out'}
    if status and status not in allowed:
        status = ''

    q = ContactImportIssue.query.filter_by(import_id=job.id)
    if status:
        q = q.filter_by(status=status)
    issues = q.order_by(ContactImportIssue.row_num).limit(1000).all()

    counts = {
        'invalid': job.issues.filter_by(status='invalid').count(),
        'duplicate_db': job.issues.filter_by(status='duplicate_db').count(),
        'duplicate_file': job.issues.filter_by(
            status='duplicate_file').count(),
        'opted_out': job.issues.filter_by(status='opted_out').count(),
    }

    return render_template('contacts/import_report.html',
                           job=job, issues=issues,
                           counts=counts, active_status=status)


@contacts_bp.route('/imports/<int:job_id>/issues.csv')
@login_required
def import_issues_csv(job_id):
    """
    Download the rows that were not imported, as a CSV that can be fixed
    and re-uploaded. Same columns as the original file plus a `_status`
    and `_reason` column for reference.
    """
    import csv as _csv
    import io as _io

    org = _org()
    job = ContactImport.query.filter_by(
        id=job_id, org_id=org.id).first_or_404()

    rows = (ContactImportIssue.query
            .filter_by(import_id=job.id)
            .order_by(ContactImportIssue.row_num)
            .all())

    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(['phone', 'name', 'group', 'district',
                '_row', '_status', '_reason'])
    for r in rows:
        w.writerow([
            r.raw_phone or '',
            r.name or '',
            r.group_name or '',
            r.district_name or '',
            r.row_num or '',
            r.status or '',
            r.reason or '',
        ])

    filename = f'import-{job.id}-issues.csv'
    return Response(
        buf.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@contacts_bp.route('/sample.csv')
@login_required
def sample_csv():
    lines = [
        'phone,name,group,district',
        '0700123456,Alice Example,VIP,Kampala',
        '0752123456,Bob Example,Newsletter,Wakiso',
        '256772123456,Carol Example,,Mbarara',
        '+256701234567,David Example,VIP,Entebbe',
        '0789123456,,,',
    ]
    content = '\n'.join(lines) + '\n'
    return Response(
        content, mimetype='text/csv',
        headers={'Content-Disposition':
                 'attachment; filename=roman-sms-contacts-sample.csv'}
    )

@contacts_bp.route('/export')
@login_required
def export():
    data = svc.export_all(_org())
    return Response(data, mimetype='text/csv',
                    headers={'Content-Disposition':
                             'attachment; filename=contacts.csv'})