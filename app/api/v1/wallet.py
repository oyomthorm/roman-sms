from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from app.models import Organization
from app.api.v1 import serializers
from app.services import entitlements
from app.models import WalletTransaction

bp = Blueprint("api_wallet", __name__, url_prefix="/api/v1/wallet")

@bp.get("")
@login_required
def summary():
    oid = current_user.org_id
    try:
        bal = entitlements.get_balance(oid)
        rate = entitlements.current_rate_ugx(oid)
    except Exception:
        # No fallbacks on money. The app must show an error, not a
        # fabricated balance or rate.
        return jsonify({
            "error": "wallet_unavailable",
            "message": "Could not load wallet. Please try again.",
        }), 503
    if bal is None or rate is None:
        return jsonify({
            "error": "wallet_unavailable",
            "message": "Could not load wallet. Please try again.",
        }), 503
    return jsonify(serializers.wallet(bal, rate, bal * rate))

@bp.get("/transactions")
@login_required
def transactions():
    limit = min(int(request.args.get("limit", 50)), 200)
    q = WalletTransaction.query.filter_by(org_id=current_user.org_id).order_by(WalletTransaction.id.desc()).limit(limit).all()
    return jsonify(serializers.paginated([
        {"id": t.id, "delta": t.delta, "reason": t.reason, "balance_after": t.balance_after, "created_at": serializers.iso(t.created_at)}
        for t in q
    ], None))
