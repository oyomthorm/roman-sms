from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.models import MessageTemplate
from app.permissions import org_scoped
from app.services import templates_svc as svc

templates_bp = Blueprint('templates', __name__)


def _org():
    return current_user.organization


@templates_bp.route('/')
@login_required
def index():
    items = svc.list_templates(_org(), user=current_user)
    return render_template('templates/list.html', templates=items)


@templates_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        try:
            svc.create_template(
                _org(),
                name=request.form.get('name', ''),
                body=request.form.get('body', ''),
                department=current_user.department,
            )
        except svc.TemplateError as e:
            flash(str(e), 'danger')
            return render_template('templates/form.html', template=None)
        flash('Template created.', 'success')
        return redirect(url_for('templates.index'))
    return render_template('templates/form.html', template=None)


@templates_bp.route('/<int:tid>/edit', methods=['GET', 'POST'])
@login_required
def edit(tid):
    t = svc.get_for_user(_org(), tid, current_user)
    if t is None:
        abort(404)
    if request.method == 'POST':
        try:
            svc.update_template(
                _org(), tid,
                name=request.form.get('name', ''),
                body=request.form.get('body', ''),
                user=current_user,
            )
        except svc.TemplateError as e:
            flash(str(e), 'danger')
        else:
            flash('Template updated.', 'success')
        return redirect(url_for('templates.index'))
    return render_template('templates/form.html', template=t)


@templates_bp.route('/<int:tid>/delete', methods=['POST'])
@login_required
def delete(tid):
    t = svc.get_for_user(_org(), tid, current_user)
    if t is None:
        abort(404)
    try:
        svc.delete_template(_org(), tid, user=current_user)
        flash('Template deleted.', 'success')
    except svc.TemplateError as e:
        flash(str(e), 'danger')
    return redirect(url_for('templates.index'))