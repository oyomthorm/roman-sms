from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash)
from flask_login import login_required, current_user

from app.services import pool as svc

settings_bp = Blueprint('settings', __name__)


def _org():
    return current_user.organization


@settings_bp.route('/')
@login_required
def index():
    org = _org()
    perm = svc.get_active_permission(org)
    history = svc.permission_history(org)
    return render_template(
        'settings/index.html',
        permission=perm,
        history=history,
        agreement_text=svc.AGREEMENT_TEXT.strip(),
        agreement_version=svc.AGREEMENT_VERSION,
    )


@settings_bp.route('/pool/grant', methods=['POST'])
@login_required
def grant_pool():
    if current_user.role != 'associate_admin':
        flash('Only organization admins can do this.', 'danger')
        return redirect(url_for('settings.index'))

    if request.form.get('agreement') != 'yes':
        flash('You must check the agreement box to continue.', 'danger')
        return redirect(url_for('settings.index'))

    try:
        perm, copied = svc.grant_permission(
            _org(), current_user,
            note=request.form.get('note', '').strip() or None)
    except svc.PoolError as e:
        flash(str(e), 'danger')
        return redirect(url_for('settings.index'))

    flash(f'Contact sharing enabled. {copied} contact'
          f'{"s" if copied != 1 else ""} added to the pool.', 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/pool/revoke', methods=['POST'])
@login_required
def revoke_pool():
    if current_user.role != 'associate_admin':
        flash('Only organization admins can do this.', 'danger')
        return redirect(url_for('settings.index'))

    try:
        perm, removed = svc.revoke_permission(
            _org(), current_user,
            note=request.form.get('note', '').strip() or None)
    except svc.PoolError as e:
        flash(str(e), 'danger')
        return redirect(url_for('settings.index'))

    flash(f'Contact sharing disabled. {removed} contact'
          f'{"s" if removed != 1 else ""} removed from the pool.', 'success')
    return redirect(url_for('settings.index'))