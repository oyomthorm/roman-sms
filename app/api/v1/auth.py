from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from app.extensions import db
from app.models import User
from app.models.api import issue_token, ApiToken
from app.api.v1 import serializers

bp = Blueprint("api_auth", __name__, url_prefix="/api/v1/auth")

@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    user = User.query.filter_by(email=(data.get("email") or "").strip().lower()).first()
    if not user or not user.check_password(data.get("password", "")):
        return jsonify({"error": "invalid_credentials", "message": "Invalid email or password"}), 401
    if hasattr(user, 'is_active') and not user.is_active:
        return jsonify({"error": "account_inactive", "message": "Account suspended"}), 403

    token = issue_token(user, data.get("device_label", "Flutter Android"))
    db.session.commit()
    from app.models import Organization
    org = Organization.query.get(user.org_id) if user.org_id else None
    return jsonify({"token": token, "user": serializers.user(user), "org": serializers.org(org) if org else None})

@bp.post("/logout")
@login_required
def logout():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        from app.models.api import _hash
        ApiToken.query.filter_by(token_hash=_hash(header[7:].strip()), user_id=current_user.id).update({"revoked_at": db.func.now()})
        db.session.commit()
    return jsonify({"ok": True})

@bp.get("/me")
@login_required
def me():
    from app.models import Organization
    org = Organization.query.get(current_user.org_id) if current_user.org_id else None
    return jsonify({"user": serializers.user(current_user), "org": serializers.org(org) if org else None})
