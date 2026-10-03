from flask_login import current_user
from app.extensions import db
from app.models import AuditLog


def log(action, detail=None, org_id=None, actor_id=None):
    try:
        if org_id is None and current_user.is_authenticated:
            org_id = current_user.org_id
        if actor_id is None and current_user.is_authenticated:
            actor_id = current_user.id
        db.session.add(AuditLog(
            action=action,
            detail=detail if isinstance(detail, str) else repr(detail),
            org_id=org_id,
            actor_id=actor_id,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()