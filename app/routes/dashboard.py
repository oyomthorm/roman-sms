from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

from app.extensions import db
from app.models import (Campaign, Contact, Group, MessageLog,
                        WalletTransaction)
from app.services.entitlements import active_subscription
from app.services.wallet import get_balance


dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/app')
@login_required
def index():
    if current_user.is_master:
        return redirect(url_for('master.index'))

    org = current_user.organization
    since = datetime.utcnow() - timedelta(days=30)

    # ---- Message stats (last 30 days) ----
    #
    # "sent" here means: reached the network and were accepted by Pahappa.
    # This is the population we compute delivery rate against. It includes
    # messages that later became delivered or delivery_failed.
    sent_30d = (MessageLog.query
                .filter_by(org_id=org.id)
                .filter(MessageLog.sent_at >= since)
                .filter(MessageLog.status.in_(
                    ['sent', 'delivered', 'delivery_failed']))
                .count())

    # Subsets of sent_30d — messages the webhook has confirmed delivery for
    delivered_30d = (MessageLog.query
                     .filter_by(org_id=org.id, status='delivered')
                     .filter(MessageLog.delivered_at >= since)
                     .count())

    delivery_failed_30d = (MessageLog.query
                           .filter_by(org_id=org.id,
                                      status='delivery_failed')
                           .filter(MessageLog.delivered_at >= since)
                           .count())

    # Independent counters (not subsets of sent_30d)
    failed_30d = (MessageLog.query
                  .filter_by(org_id=org.id, status='failed')
                  .filter(MessageLog.created_at >= since)
                  .count())

    pending_30d = (MessageLog.query
                   .filter_by(org_id=org.id, status='pending')
                   .filter(MessageLog.created_at >= since)
                   .count())

    # ---- Daily send trend (last 30 days, includes zero-days) ----
    rows = (db.session.query(
                db.func.date(MessageLog.sent_at).label('d'),
                db.func.count(MessageLog.id))
            .filter(MessageLog.org_id == org.id)
            .filter(MessageLog.sent_at >= since)
            .filter(MessageLog.status.in_(
                ['sent', 'delivered', 'delivery_failed']))
            .group_by(db.func.date(MessageLog.sent_at))
            .all())

    by_day = {str(r[0]): r[1] for r in rows}
    today = date.today()
    trend = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        trend.append({'date': d, 'count': by_day.get(str(d), 0)})

    trend_max = max((t['count'] for t in trend), default=0)

    # ---- Credit burn rate (last 30 days) ----
    credits_spent_30d = -int((db.session.query(
                                db.func.coalesce(
                                    db.func.sum(WalletTransaction.delta), 0))
                              .filter_by(org_id=org.id,
                                         reason='sms_send')
                              .filter(WalletTransaction.created_at >= since)
                              .scalar()) or 0)

    avg_daily_spend = credits_spent_30d / 30.0 if credits_spent_30d else 0
    balance_now = get_balance(org.id)

    if avg_daily_spend > 0:
        days_remaining = int(balance_now / avg_daily_spend)
    else:
        days_remaining = None   # no sends = nothing to burn

    stats = {
        'contacts': Contact.query.filter_by(org_id=org.id).count(),
        'groups': Group.query.filter_by(org_id=org.id).count(),
        'campaigns': Campaign.query.filter_by(org_id=org.id).count(),
        'sent_30d': sent_30d,
        'delivered_30d': delivered_30d,
        'delivery_failed_30d': delivery_failed_30d,
        'failed_30d': failed_30d,
        'pending_30d': pending_30d,
        'credits_spent_30d': credits_spent_30d,
        'avg_daily_spend': round(avg_daily_spend, 1),
        'days_remaining': days_remaining,
    }

    recent = (Campaign.query
              .filter_by(org_id=org.id)
              .order_by(Campaign.id.desc())
              .limit(8)
              .all())

    return render_template(
        'dashboard/index.html',
        org=org,
        stats=stats,
        trend=trend,
        trend_max=trend_max,
        balance=balance_now,
        subscription=active_subscription(org.id),
        recent=recent,
    )