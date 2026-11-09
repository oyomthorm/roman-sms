from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Contact, OptOut
from app.services import contacts as contacts_svc
from app.services import geo as geo_svc
from app.services import groups as svc

groups_bp = Blueprint('groups', __name__)


def _org():
    return current_user.organization


@groups_bp.route('/')
@login_required
def index():
    rows = svc.list_groups(_org(), user=current_user)
    return render_template('groups/list.html', rows=rows)


@groups_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        try:
            svc.create(_org(),
                       name=request.form.get('name', ''),
                       description=request.form.get('description', ''),
                       department=current_user.department,
                       actor_id=current_user.id)
        except svc.GroupError as e:
            flash(str(e), 'danger')
            return render_template('groups/form.html', group=None,
                                   form=request.form)
        flash('Group created.', 'success')
        return redirect(url_for('groups.index'))
    return render_template('groups/form.html', group=None, form={})


@groups_bp.route('/<int:gid>')
@login_required
def detail(gid):
    org = _org()
    group = svc.get_for_user(org, gid, current_user)
    if not group:
        return render_template('errors/404.html'), 404
    contacts = svc.contacts_in(org, gid)
    return render_template('groups/detail.html',
                           group=group, contacts=contacts)


@groups_bp.route('/<int:gid>/edit', methods=['GET', 'POST'])
@login_required
def edit(gid):
    org = _org()
    group = svc.get_for_user(org, gid, current_user)
    if not group:
        return render_template('errors/404.html'), 404

    if request.method == 'POST':
        try:
            svc.update(org, gid,
                       name=request.form.get('name', ''),
                       description=request.form.get('description', ''),
                       actor_id=current_user.id)
        except svc.GroupError as e:
            flash(str(e), 'danger')
        else:
            flash('Group updated.', 'success')
            return redirect(url_for('groups.index'))
    return render_template('groups/form.html', group=group, form={})


@groups_bp.route('/<int:gid>/delete', methods=['GET', 'POST'])
@login_required
def delete(gid):
    org = _org()
    group = svc.get_for_user(org, gid, current_user)
    if not group:
        return render_template('errors/404.html'), 404

    contact_count = len(svc.contacts_in(org, gid))

    if request.method == 'POST':
        move_to = request.form.get('move_to', '').strip()
        move_to_id = int(move_to) if move_to.isdigit() else None
        try:
            moved, target = svc.delete(org, gid,
                                       move_to_group_id=move_to_id,
                                       actor_id=current_user.id)
        except svc.GroupError as e:
            flash(str(e), 'danger')
            return redirect(url_for('groups.delete', gid=gid))

        if moved:
            where = target.name if target else 'no group'
            flash(f'Deleted "{group.name}". Moved {moved} contact(s) '
                  f'to {where}.', 'success')
        else:
            flash(f'Deleted "{group.name}".', 'success')
        return redirect(url_for('groups.index'))

    other_groups = [g for g, _ in svc.list_groups(org, user=current_user) if g.id != gid]
    return render_template('groups/delete.html',
                           group=group,
                           contact_count=contact_count,
                           other_groups=other_groups)


@groups_bp.route('/<int:gid>/import', methods=['GET', 'POST'])
@login_required
def import_to_group(gid):
    org = _org()
    group = svc.get_for_user(org, gid, current_user)
    if not group:
        return render_template('errors/404.html'), 404

    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename:
            flash('No file uploaded.', 'danger')
            return redirect(url_for('groups.import_to_group', gid=gid))

        on_duplicate = request.form.get('on_duplicate', 'skip').strip()
        if on_duplicate not in ('skip', 'update'):
            on_duplicate = 'skip'

        district_id_raw = request.form.get('district_id', '').strip()
        district_id = int(district_id_raw) if district_id_raw.isdigit() else None

        try:
            job = contacts_svc.import_csv(
                org, file.stream,
                default_group=group.name,
                default_district_id=district_id,
                on_duplicate=on_duplicate,
                filename=file.filename,
                user_id=current_user.id,
            )
        except contacts_svc.ContactError as e:
            flash(str(e), 'danger')
            return redirect(url_for('groups.import_to_group', gid=gid))

        return redirect(url_for('contacts.import_report', job_id=job.id))

    # GET: mirror contacts.import_page context
    existing_phones = [
        row[0] for row in
        db.session.query(Contact.phone)
        .filter_by(org_id=org.id)
        .order_by(Contact.id.desc())
        .limit(5000)
        .all()
    ]
    opt_out_phones = [
        row[0] for row in
        db.session.query(OptOut.phone)
        .order_by(OptOut.id.desc())
        .limit(5000)
        .all()
    ]

    return render_template('contacts/import.html',
                           preset_group=group,
                           groups=svc.list_groups(org, user=current_user),
                           districts_by_region=geo_svc.list_by_region(),
                           existing_phones=existing_phones,
                           opt_out_phones=opt_out_phones)