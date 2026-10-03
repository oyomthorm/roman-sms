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


def org_scoped(model):
    """Every read of tenant data must go through this."""
    if current_user.is_authenticated and current_user.role == 'master_admin':
        return model.query
    return model.query.filter_by(org_id=current_user.org_id)