from flask import Blueprint, jsonify
from flask_login import current_user, login_required
from app.models import NotificationDismissal, Organization
from app.services import entitlements

bp = Blueprint("api_notifications", __name__, url_prefix="/api/v1/notifications")

@bp.get("")
@login_required
def index():
    items = []
    
    # Condition 1: Low Wallet Balance
    try:
        balance = entitlements.balance(current_user.org_id) or 0
        if balance < 100:
            items.append({
                "key": f"low_balance_{balance}",
                "type": "warning",
                "title": "Low SMS Balance",
                "body": f"You only have {balance} SMS left. Top up soon to avoid interruptions."
            })
    except Exception:
        pass

    # Filter out dismissed notifications
    dismissed = [d.key for d in NotificationDismissal.query.filter_by(user_id=current_user.id).all()]
    items = [i for i in items if i["key"] not in dismissed]

    return jsonify({"items": items})

@bp.post("/<path:key>/dismiss")
@login_required
def dismiss(key):
    db_dismiss = NotificationDismissal.query.filter_by(user_id=current_user.id, key=key).first()
    if not db_dismiss:
        from app.extensions import db
        db.session.add(NotificationDismissal(user_id=current_user.id, key=key))
        db.session.commit()
    return jsonify({"ok": True})
