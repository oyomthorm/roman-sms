from flask import Blueprint, request, jsonify, g
from flask_login import current_user, login_required
from app.models import Organization
from app.extensions import db
from app.api.v1 import serializers
from app.api.v1.utils import require_idempotency
from app.models import Campaign, MessageLog, ApiIdempotency
from app.services import campaigns as camp_svc
from app.services import renderer, entitlements

bp = Blueprint("api_campaigns", __name__, url_prefix="/api/v1/campaigns")

@bp.post("/preview")
@login_required
def preview():
    body = (request.get_json(silent=True) or {}).get("body", "")
    prefix = getattr(Organization.query.get(current_user.org_id), "brand_name", "")
    rendered = f"{prefix}: {body}" if prefix else body
    chars = len(rendered)
    segments = renderer.segments(chars)
    rate = entitlements.current_rate_ugx(current_user.org_id)
    return jsonify({"characters": chars, "segments": segments, "cost_credits": segments, "cost_ugx": segments * rate, "rate_ugx": rate})

@bp.get("")
@login_required
def index():
    camps = Campaign.query.filter_by(org_id=current_user.org_id).order_by(Campaign.id.desc()).limit(50).all()
    return jsonify(serializers.paginated([serializers.campaign(c) for c in camps], None))

@bp.get("/<int:id>")
@login_required
def detail(id):
    c = Campaign.query.filter_by(id=id, org_id=current_user.org_id).first_or_404()
    breakdown = dict(db.session.query(MessageLog.status, db.func.count(MessageLog.id)).filter(MessageLog.campaign_id == c.id).group_by(MessageLog.status).all())
    res = serializers.campaign(c)
    res["breakdown"] = breakdown
    return jsonify(res)

@bp.post("")
@login_required
@require_idempotency
def create():
    data = request.get_json(silent=True) or {}
    body = data.get("body", "").strip()
    if not body: return jsonify({"error": "empty_body"}), 422

    synthetic = None
    if data.get("recipient_source") == "paste":
        report = camp_svc.resolve_pasted_numbers(data.get("pasted_numbers", ""))
        if not report.accepted: return jsonify({"error": "no_recipients", "report": report.as_dict()}), 422
        synthetic = report.accepted

    try:
        camp = camp_svc.create_campaign(
            org=Organization.query.get(current_user.org_id), name=data.get("name", "SMS Campaign"), body=body,
            synthetic_contacts=synthetic, commit=False
        )
    except Exception as e:
        return jsonify({"error": "campaign_failed", "message": str(e)}), 400

    res = serializers.campaign(camp)
    
    # Save idempotent response
    ApiIdempotency.query.filter_by(user_id=current_user.id, key=g.idempotency_key).update(
        {"response_status": 201, "response_body": res}
    )
    db.session.commit()
    return jsonify(res), 201
