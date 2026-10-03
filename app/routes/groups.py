from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.services import groups as svc

groups_bp = Blueprint('groups', __name__)


def _org():
    return current_user.organization


@groups_bp.route('/')
@login_required
def index():
    rows = svc.list_groups(_org())
    return render_template('groups/list.html', rows=rows)


@groups_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        try:
            svc.create(_org(),
                       name=request.form.get('name', ''),
                       description=request.form.get('description', ''),
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
    group = svc.get(org, gid)
    if not group:
        return render_template('errors/404.html'), 404
    contacts = svc.contacts_in(org, gid)
    return render_template('groups/detail.html',
                           group=group, contacts=contacts)


@groups_bp.route('/<int:gid>/edit', methods=['GET', 'POST'])
@login_required
def edit(gid):
    org = _org()
    group = svc.get(org, gid)
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
    group = svc.get(org, gid)
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

    other_groups = [g for g, _ in svc.list_groups(org) if g.id != gid]
    return render_template('groups/delete.html',
                           group=group,
                           contact_count=contact_count,
                           other_groups=other_groups)