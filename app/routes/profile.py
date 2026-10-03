from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.services import users as svc
from app.services.wallet import get_balance
from app.services.subscriptions import current_for as current_subscription


profile_bp = Blueprint('profile', __name__)


@profile_bp.route('/', methods=['GET'])
@login_required
def index():
    org = current_user.organization

    # Sidebar stats — useful even though this is a profile page.
    balance = None
    subscription = None
    if not current_user.is_master:
        balance = get_balance(org.id)
        subscription = current_subscription(org.id)

    return render_template(
        'profile/index.html',
        org=org,
        balance=balance,
        subscription=subscription,
    )


@profile_bp.route('/update', methods=['POST'])
@login_required
def update():
    try:
        svc.update_profile(
            current_user,
            full_name=request.form.get('full_name', ''),
            email=request.form.get('email', ''),
        )
    except svc.UserError as e:
        flash(str(e), 'danger')
        return redirect(url_for('profile.index'))

    flash('Profile updated.', 'success')
    return redirect(url_for('profile.index'))


@profile_bp.route('/password', methods=['POST'])
@login_required
def change_password():
    try:
        svc.change_password(
            current_user,
            current_password=request.form.get('current_password', ''),
            new_password=request.form.get('new_password', ''),
            confirm_password=request.form.get('confirm_password', ''),
        )
    except svc.UserError as e:
        flash(str(e), 'danger')
        return redirect(url_for('profile.index'))

    flash('Password changed.', 'success')
    return redirect(url_for('profile.index'))