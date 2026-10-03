"""
User service for self-service profile operations.

Role assignment and user creation live in services/orgs.py — this module
only handles a user editing their own account.
"""
import re

from app.extensions import db
from app.models import User
from app.services.audit import log as audit


EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


class UserError(Exception):
    pass


def _validate_email(email, exclude_id=None):
    email = (email or '').strip().lower()
    if not EMAIL_RE.match(email):
        raise UserError('Enter a valid email address.')

    q = User.query.filter(User.email == email)
    if exclude_id:
        q = q.filter(User.id != exclude_id)
    if q.first():
        raise UserError('That email is already in use.')
    return email


def _validate_password(pw):
    if not pw or len(pw) < 8:
        raise UserError('Password must be at least 8 characters.')
    if pw.isdigit():
        raise UserError('Password cannot be all numbers.')
    return pw


def update_profile(user, *, full_name=None, email=None):
    """Update the basic identity fields. Does not touch password or role."""
    if full_name is not None:
        user.full_name = full_name.strip() or None

    if email is not None and email.strip().lower() != user.email:
        user.email = _validate_email(email, exclude_id=user.id)

    db.session.commit()
    audit('user_update_profile', user.email, org_id=user.org_id, actor_id=user.id)
    return user


def change_password(user, *, current_password, new_password, confirm_password):
    if not user.check_password(current_password or ''):
        raise UserError('Current password is incorrect.')

    _validate_password(new_password)

    if new_password != confirm_password:
        raise UserError('New passwords do not match.')

    if user.check_password(new_password):
        raise UserError('New password must be different from the current one.')

    user.set_password(new_password)
    db.session.commit()
    audit('user_change_password', user.email, org_id=user.org_id, actor_id=user.id)
    return user