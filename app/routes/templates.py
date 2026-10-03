from flask import Blueprint, render_template, request, redirect, url_for, flash
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
    items = svc.list_templates(_org())
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
    t = org_scoped(MessageTemplate).filter_by(id=tid).first_or_404()
    if request.method == 'POST':
        try:
            svc.update_template(
                _org(), tid,
                name=request.form.get('name', ''),
                body=request.form.get('body', ''),
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
    try:
        svc.delete_template(_org(), tid)
        flash('Template deleted.', 'success')
    except svc.TemplateError as e:
        flash(str(e), 'danger')
    return redirect(url_for('templates.index'))