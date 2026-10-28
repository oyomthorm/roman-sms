from flask import Blueprint, request, jsonify, g
from flask_login import current_user, login_required
from app.models import Organization
from app.extensions import db
from app.api.v1 import serializers
from app.api.v1.utils import require_idempotency
from app.models import Campaign, MessageLog, ApiIdempotency
from app.services import campaigns as camp_svc
from app.services import phones as phones_svc
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
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "empty_body"}), 422

    source = data.get("recipient_source", "contacts")
    custom_phones = None

    if source == "paste":
        text = data.get("pasted_numbers", "") or ""
        # parse_pasted_numbers is the same normalizer the web route uses
        # (app/routes/campaigns.py). It returns normalized, deduped
        # numbers with the platform cap already applied.
        try:
            custom_phones = phones_svc.parse_pasted_numbers(text)
        except TypeError:
            # Signature mismatch — fall back to the simpler normalize path
            # so the error surfaces as an empty list rather than 500.
            from app.services.phones import normalize_ug
            custom_phones = []
            for raw in (text.splitlines() or []):
                norm = normalize_ug(raw)
                if norm and norm not in custom_phones:
                    custom_phones.append(norm)
        if not custom_phones:
            return jsonify({
                "error": "no_valid_recipients",
                "message": "No valid phone numbers in the pasted list.",
            }), 422
        if len(custom_phones) > 500:
            return jsonify({
                "error": "too_many_recipients",
                "message": "Pasted list exceeds the 500 number cap.",
                "count": len(custom_phones),
            }), 422
    elif source != "contacts":
        return jsonify({
            "error": "invalid_recipient_source",
            "message": "recipient_source must be 'contacts' or 'paste'.",
            "got": source,
        }), 422

    try:
        camp = camp_svc.create_campaign(
            org=Organization.query.get(current_user.org_id),
            name=data.get("name", "SMS Campaign"),
            body=body,
            custom_phones=custom_phones,
            created_by=current_user.id,
        )
    except Exception as e:
        return jsonify({"error": "campaign_failed", "message": str(e)}), 400

    res = serializers.campaign(camp)

    ApiIdempotency.query.filter_by(
        user_id=current_user.id, key=g.idempotency_key,
    ).update({"response_status": 201, "response_body": res})
    db.session.commit()
    return jsonify(res), 201