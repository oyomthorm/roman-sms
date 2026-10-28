from flask import Blueprint, jsonify
from flask_login import login_required
from app.models import Plan
bp = Blueprint("api_plans", __name__, url_prefix="/api/v1/plans")

@bp.get("")
@login_required
def index():
    plans = Plan.query.filter_by(is_active=True).order_by(Plan.credits.asc()).all()
    return jsonify({"items": [{"id": p.id, "name": p.name, "credits": p.credits, "price_ugx": p.price_ugx, "rate_ugx": p.rate_ugx} for p in plans]})
