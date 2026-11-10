"""School-admin user management routes.

Per docs/DEPARTMENTS.md §1: an org-level school admin (associate_admin with
department=None) manages users in their own org. Master does not use these
routes; master's only user-level action on an org is reset_admin_password.
"""
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash)
from flask_login import login_required, current_user

from app.models import User
from app.permissions import school_admin_required
from app.services import orgs as orgs_svc


school_bp = Blueprint('school', __name__)


@school_bp.route('/users')
@login_required
@school_admin_required
def users():
    org = current_user.organization
    rows = orgs_svc.list_users(org)
    return render_template('school/users.html', users=rows, org=org)


@school_bp.route('/users/new', methods=['GET', 'POST'])
@login_required
@school_admin_required
def user_new():
    org = current_user.organization
    if request.method == 'POST':
        try:
            user = orgs_svc.create_user(
                org,
                email=request.form.get('email', ''),
                full_name=request.form.get('full_name', ''),
                password=request.form.get('password', ''),
                role=request.form.get('role', 'associate_admin'),
                department=(request.form.get('department') or None),
                actor_id=current_user.id,
            )
        except orgs_svc.OrgError as e:
            flash(str(e), 'danger')
            return render_template(
                'school/user_form.html',
                user=None, form=request.form,
                departments=orgs_svc.DEPARTMENTS,
                roles=orgs_svc.USER_ROLES)
        flash(f'User {user.email} created.', 'success')
        return redirect(url_for('school.users'))
    return render_template(
        'school/user_form.html',
        user=None, form={},
        departments=orgs_svc.DEPARTMENTS,
        roles=orgs_svc.USER_ROLES)


@school_bp.route('/users/<int:uid>/edit', methods=['GET', 'POST'])
@login_required
@school_admin_required
def user_edit(uid):
    org = current_user.organization
    user = User.query.filter_by(id=uid, org_id=org.id).first()
    if not user:
        return render_template('errors/404.html'), 404

    if request.method == 'POST':
        try:
            orgs_svc.update_user(
                org, uid,
                full_name=request.form.get('full_name', ''),
                email=request.form.get('email', ''),
                department=(request.form.get('department') or None),
                actor_id=current_user.id,
            )
        except orgs_svc.OrgError as e:
            flash(str(e), 'danger')
        else:
            flash('User updated.', 'success')
            return redirect(url_for('school.users'))

    return render_template(
        'school/user_form.html',
        user=user, form={},
        departments=orgs_svc.DEPARTMENTS,
        roles=orgs_svc.USER_ROLES)


@school_bp.route('/users/<int:uid>/delete', methods=['POST'])
@login_required
@school_admin_required
def user_delete(uid):
    org = current_user.organization
    try:
        orgs_svc.delete_user(org, uid, actor_id=current_user.id)
        flash('User deleted.', 'success')
    except orgs_svc.OrgError as e:
        flash(str(e), 'danger')
    return redirect(url_for('school.users'))


@school_bp.route('/users/<int:uid>/reset-password', methods=['POST'])
@login_required
@school_admin_required
def user_reset_password(uid):
    org = current_user.organization
    try:
        user = orgs_svc.reset_admin_password(
            org, uid,
            request.form.get('new_password', ''),
            actor_id=current_user.id)
        flash(f'Password reset for {user.email}.', 'success')
    except orgs_svc.OrgError as e:
        flash(str(e), 'danger')
    return redirect(url_for('school.users'))
@school_bp.route('/users/<int:uid>/suspend', methods=['POST'])
@login_required
@school_admin_required
def user_suspend(uid):
    org = current_user.organization
    try:
        orgs_svc.suspend_user(org, uid, actor_id=current_user.id)
        flash('User suspended.', 'success')
    except orgs_svc.OrgError as e:
        flash(str(e), 'danger')
    return redirect(url_for('school.users'))


@school_bp.route('/users/<int:uid>/terminate', methods=['POST'])
@login_required
@school_admin_required
def user_terminate(uid):
    org = current_user.organization
    try:
        orgs_svc.terminate_user(org, uid, actor_id=current_user.id)
        flash('User terminated.', 'success')
    except orgs_svc.OrgError as e:
        flash(str(e), 'danger')
    return redirect(url_for('school.users'))


@school_bp.route('/users/<int:uid>/reactivate', methods=['POST'])
@login_required
@school_admin_required
def user_reactivate(uid):
    org = current_user.organization
    try:
        orgs_svc.reactivate_user(org, uid, actor_id=current_user.id)
        flash('User reactivated.', 'success')
    except orgs_svc.OrgError as e:
        flash(str(e), 'danger')
    return redirect(url_for('school.users'))

@school_bp.route('/users/<int:uid>')
@login_required
@school_admin_required
def user_detail(uid):
    """Read-only activity summary for one user."""
    org = current_user.organization
    user = orgs_svc.get_user(org, uid)
    if not user:
        return render_template('errors/404.html'), 404
    activity = orgs_svc.get_user_activity(org, uid)
    return render_template('school/user_detail.html',
                           org=org, user=user, activity=activity)
