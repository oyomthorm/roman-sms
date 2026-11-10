from sqlalchemy import or_

from functools import wraps
from flask import abort
from flask_login import current_user


def role_required(*allowed_roles):
    def deco(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in allowed_roles:
                abort(403)
            return f(*a, **kw)
        return wrapper
    return deco


def master_required(f):
    return role_required('master_admin')(f)


def org_admin_required(f):
    return role_required('master_admin', 'associate_admin')(f)



def school_admin_required(f):
    """Requires current_user to be an org-level school admin.

    That is: role='associate_admin' AND department IS NULL.
    Master is explicitly rejected. Dept-scoped users are rejected.
    Per docs/DEPARTMENTS.md §1 -- user management is org-admin-only.
    """
    @wraps(f)
    def wrapper(*a, **kw):
        if not current_user.is_authenticated:
            abort(401)
        if current_user.role != 'associate_admin':
            abort(403)
        if getattr(current_user, 'department', None) is not None:
            abort(403)
        return f(*a, **kw)
    return wrapper
def org_scoped(model):
    """Every read of tenant data must go through this."""
    if current_user.is_authenticated and current_user.role == 'master_admin':
        return model.query
    return model.query.filter_by(org_id=current_user.org_id)

def department_filter(query, model, user):
    """Filter a query by the current user's department visibility.

    - user.department is None       -> sees everything in the org
    - record.department is None     -> shared, visible to all
    - record.department matches     -> visible to that department only

    A user with department='bursar' sees records where
    department='bursar' OR department IS NULL, never 'dos'.

    Usage:
        q = Group.query.filter_by(org_id=org.id)
        q = department_filter(q, Group, current_user)
    """
    if user is None or getattr(user, 'department', None) is None:
        return query
    return query.filter(
        or_(model.department == user.department,
            model.department.is_(None))
    )
