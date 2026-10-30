from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from app.extensions import db
from app.models import User
from app.models.api import issue_token, ApiToken
from app.api.v1 import serializers
from flask import current_app
from app.extensions import limiter
from app.services import signups as signups_svc

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

@bp.post("/signup")
@limiter.limit("5 per hour")
def signup():
    if not current_app.config.get("SIGNUP_ENABLED", True):
        return jsonify({"error": "signups_closed",
                        "message": "Signups are temporarily closed."}), 403

    data = request.get_json(silent=True) or {}

    # Honeypot: mobile always sends website="" — a non-empty value means a bot
    # filling the raw JSON, and we silently accept-then-drop like the web route.
    if data.get("website"):
        return jsonify({"ok": True, "created": False,
                        "message": "Thanks. If approved, we'll email you."}), 200

    try:
        req, created = signups_svc.submit_request(
            company_name=data.get("company_name", ""),
            desired_slug=data.get("desired_slug", ""),
            brand_name=data.get("brand_name") or data.get("company_name", ""),
            contact_name=data.get("contact_name", ""),
            contact_email=data.get("contact_email", ""),
            contact_phone=data.get("contact_phone"),
            district_id=data.get("district_id"),
            plan_id=data.get("plan_id"),
            expected_volume=data.get("expected_volume"),
            message=data.get("message"),
            ip_address=request.remote_addr,
            user_agent=(request.headers.get("User-Agent") or "")[:255],
        )
    except signups_svc.SignupError as e:
        return jsonify({"error": "signup_invalid", "message": str(e)}), 422
    except Exception:
        current_app.logger.exception("API signup failed")
        return jsonify({"error": "server_error",
                        "message": "Could not submit your application. Try again."}), 500

    return jsonify({
        "ok": True,
        "created": created,
        "request_id": req.id,
        "message": "Thanks. If approved, we'll email you with a link to set your password.",
    }), 201
@bp.put("/profile")
@login_required
def update_profile():
    from app.services import users as users_svc
    data = request.get_json(silent=True) or {}
    kwargs = {}
    if "full_name" in data:
        kwargs["full_name"] = data["full_name"]
    if not kwargs:
        return jsonify({"error": "no_fields", "message": "Nothing to update."}), 422
    try:
        users_svc.update_profile(current_user, **kwargs)
    except users_svc.UserError as e:
        return jsonify({"error": "invalid_profile", "message": str(e)}), 422
    return jsonify(serializers.user(current_user)), 200


@bp.post("/change-password")
@login_required
def change_password():
    from app.services import users as users_svc
    data = request.get_json(silent=True) or {}
    try:
        users_svc.change_password(
            current_user,
            current_password=data.get("current_password", ""),
            new_password=data.get("new_password", ""),
            confirm_password=data.get("new_password", ""),
        )
    except users_svc.UserError as e:
        return jsonify({"error": "invalid_password", "message": str(e)}), 422
    return jsonify({"ok": True}), 200
