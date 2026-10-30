from datetime import datetime, timedelta

from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (Campaign, Contact, Group, MessageLog,
                        WalletTransaction)
from app.services.entitlements import current_rate_ugx
from app.services.wallet import get_balance


bp = Blueprint("api_dashboard", __name__, url_prefix="/api/v1/dashboard")


@bp.get("")
@login_required
def index():
    org_id = current_user.org_id
    since = datetime.utcnow() - timedelta(days=30)

    # ---- Message counters (same formulas as app/routes/dashboard.py) ----
    sent_30d = (MessageLog.query
                .filter_by(org_id=org_id)
                .filter(MessageLog.sent_at >= since)
                .filter(MessageLog.status.in_(
                    ['sent', 'delivered', 'delivery_failed']))
                .count())

    delivered_30d = (MessageLog.query
                     .filter_by(org_id=org_id, status='delivered')
                     .filter(MessageLog.delivered_at >= since)
                     .count())

    delivery_failed_30d = (MessageLog.query
                           .filter_by(org_id=org_id, status='delivery_failed')
                           .filter(MessageLog.delivered_at >= since)
                           .count())

    failed_30d = (MessageLog.query
                  .filter_by(org_id=org_id, status='failed')
                  .filter(MessageLog.created_at >= since)
                  .count())

    pending_30d = (MessageLog.query
                   .filter_by(org_id=org_id, status='pending')
                   .filter(MessageLog.created_at >= since)
                   .count())

    if sent_30d > 0:
        delivery_rate = "%.1f%%" % (delivered_30d / sent_30d * 100.0)
    else:
        delivery_rate = "\u2014"

    # ---- Credit spend (30d) ----
    credits_spent_30d = -int((db.session.query(
                                db.func.coalesce(
                                    db.func.sum(WalletTransaction.delta), 0))
                              .filter_by(org_id=org_id, reason='sms_send')
                              .filter(WalletTransaction.created_at >= since)
                              .scalar()) or 0)

    avg_daily_spend = credits_spent_30d / 30.0 if credits_spent_30d else 0
    balance_now = get_balance(org_id)
    days_remaining = int(balance_now / avg_daily_spend) if avg_daily_spend > 0 else None

    # ---- Recent activity (last 5 transactions) ----
    rate_ugx = current_rate_ugx(org_id)
    txs = (WalletTransaction.query
           .filter_by(org_id=org_id)
           .order_by(WalletTransaction.id.desc())
           .limit(5)
           .all())
    recent_activity = [_activity(tx, rate_ugx) for tx in txs]

    return jsonify({
        "contacts": Contact.query.filter_by(org_id=org_id).count(),
        "groups": Group.query.filter_by(org_id=org_id).count(),
        "campaigns": Campaign.query.filter_by(org_id=org_id).count(),
        "sent_30d": sent_30d,
        "delivered_30d": delivered_30d,
        "delivery_failed_30d": delivery_failed_30d,
        "failed_30d": failed_30d,
        "pending_30d": pending_30d,
        "delivery_rate": delivery_rate,
        "credits_spent_30d": credits_spent_30d,
        "avg_daily_spend": round(avg_daily_spend, 1),
        "days_remaining": days_remaining,
        "balance": balance_now,
        "recent_activity": recent_activity,
    }), 200


def _activity(tx, rate_ugx):
    is_credit = tx.delta > 0
    amount_ugx = int(abs(tx.delta) * rate_ugx)
    sign = "+" if is_credit else "-"
    return {
        "type": "credit" if is_credit else "debit",
        "title": _title(tx),
        "date": _date(tx.created_at),
        "amount": "%s %s" % (sign, "{:,}".format(amount_ugx)),
    }


def _title(tx):
    reason = tx.reason or ""
    if reason == "sms_send":
        return "Campaign: %s" % (tx.note or "send")
    if reason == "plan_grant":
        return "Plan purchase"
    if reason == "refund":
        return "Refund"
    if reason == "manual_topup":
        return "Wallet top-up"
    if reason == "pahappa_sync":
        return "Sync"
    return reason.replace("_", " ").capitalize() or "Transaction"


def _date(dt):
    if dt is None:
        return ""
    now = datetime.utcnow()
    if dt.date() == now.date():
        return "Today, " + _fmt_time(dt)
    yesterday = (now - timedelta(days=1)).date()
    if dt.date() == yesterday:
        return "Yesterday, " + _fmt_time(dt)
    return dt.strftime("%d %b %Y")


def _fmt_time(dt):
    h = dt.hour % 12 or 12
    return "%d:%02d %s" % (h, dt.minute, "AM" if dt.hour < 12 else "PM")