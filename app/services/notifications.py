"""
Computed notifications with per-user dismissal.

Each notification has:
  type        — 'success' | 'danger' | 'warning' | 'info'
  title       — string
  body        — string (optional)
  url         — string
  when        — datetime
  key         — stable string; two conditions with the same key are "the
                same notification". None if non-dismissible.
  dismissible — bool

Dismissed notifications are filtered out before the list is returned.
"""
from datetime import datetime, timedelta

from app.extensions import db
from app.models import (Campaign, Invoice, MessageLog, NotificationDismissal,
                        Organization, SendQueue, Subscription)
from app.services.wallet import get_balance


LOW_BALANCE_THRESHOLD = 100
CAMPAIGN_RECENT_DAYS = 7
INVOICE_AGE_HOURS = 24
SUBSCRIPTION_WARN_DAYS = 7
FAILED_WARN_COUNT = 5


def for_user(user):
    """Return list of undismissed notification dicts, newest first."""
    if user.is_master:
        items = _for_master(user)
    else:
        items = _for_associate(user)

    dismissed = _dismissed_keys(user)
    items = [n for n in items
             if not (n.get('key') and n['key'] in dismissed)]

    items.sort(key=lambda x: x.get('when') or datetime.utcnow(), reverse=True)
    return items


# --------------------------------------------------------------------------
# Dismissal
# --------------------------------------------------------------------------

def _dismissed_keys(user):
    rows = (NotificationDismissal.query
            .filter_by(user_id=user.id)
            .with_entities(NotificationDismissal.key)
            .all())
    return {r[0] for r in rows}


def dismiss(user, key):
    """Dismiss one notification for this user. Idempotent."""
    key = (key or '').strip()
    if not key:
        return False
    existing = (NotificationDismissal.query
                .filter_by(user_id=user.id, key=key)
                .first())
    if existing:
        return False
    db.session.add(NotificationDismissal(user_id=user.id, key=key))
    db.session.commit()
    return True


def dismiss_all(user):
    """Dismiss every currently-visible notification for this user."""
    items = for_user(user)
    keys = {n['key'] for n in items if n.get('key')}
    if not keys:
        return 0

    now = datetime.utcnow()
    added = 0
    for key in keys:
        existing = (NotificationDismissal.query
                    .filter_by(user_id=user.id, key=key)
                    .first())
        if not existing:
            db.session.add(NotificationDismissal(
                user_id=user.id, key=key, dismissed_at=now))
            added += 1
    db.session.commit()
    return added


# --------------------------------------------------------------------------
# Associate notifications
# --------------------------------------------------------------------------

def _for_associate(user):
    from app.services import chat as chat_svc

    org = user.organization
    now = datetime.utcnow()
    items = []

    # Chat unread — not dismissible, it clears when the user reads.
    chat_unread = chat_svc.total_unread(user)
    if chat_unread:
        items.append({
            'type': 'info',
            'title': f'{chat_unread} new chat message'
                     f'{"s" if chat_unread != 1 else ""}',
            'body': 'Open chat to read.',
            'url': '/chat/',
            'when': now,
            'key': None,
            'dismissible': False,
        })

    # Low balance — key includes the value, so it re-fires after further use.
    balance = get_balance(org.id)
    if balance < LOW_BALANCE_THRESHOLD:
        items.append({
            'type': 'warning',
            'title': 'Low credit balance',
            'body': f'You have {balance} credits remaining.',
            'url': '/billing/wallet',
            'when': now,
            'key': f'low_balance:{org.id}:{balance}',
            'dismissible': True,
        })

    # Plan expiring soon — keyed by subscription id.
    sub = (Subscription.query
           .filter_by(org_id=org.id, status='active')
           .filter(Subscription.expires_at > now)
           .order_by(Subscription.id.desc())
           .first())
    if sub:
        days_left = (sub.expires_at - now).days
        if days_left <= SUBSCRIPTION_WARN_DAYS:
            items.append({
                'type': 'warning',
                'title': 'Plan expiring soon',
                'body': f'{sub.plan.name} expires on '
                        f'{sub.expires_at.strftime("%d %b")}.',
                'url': '/billing/plans',
                'when': now,
                'key': f'plan_expiring:{sub.id}',
                'dismissible': True,
            })

    # Recently completed campaigns — keyed by campaign id.
    since = now - timedelta(days=CAMPAIGN_RECENT_DAYS)
    recent = (Campaign.query
              .filter_by(org_id=org.id, status='complete')
              .filter(Campaign.completed_at >= since)
              .order_by(Campaign.completed_at.desc())
              .limit(5)
              .all())
    for c in recent:
        items.append({
            'type': 'success',
            'title': f'{c.name} sent',
            'body': f'{c.sent_count or 0} delivered'
                    + (f', {c.failed_count} failed' if c.failed_count else ''),
            'url': f'/campaigns/{c.id}',
            'when': c.completed_at,
            'key': f'campaign_sent:{c.id}',
            'dismissible': True,
        })

    # Unpaid invoices older than 24h — keyed by invoice id.
    old_cutoff = now - timedelta(hours=INVOICE_AGE_HOURS)
    old_invoices = (Invoice.query
                    .filter_by(org_id=org.id, status='unpaid')
                    .filter(Invoice.issued_at < old_cutoff)
                    .order_by(Invoice.issued_at.desc())
                    .all())
    for i in old_invoices:
        items.append({
            'type': 'info',
            'title': f'Invoice {i.number} awaiting payment',
            'body': f'{i.currency} {i.amount:,.0f} for {i.plan_name}.',
            'url': f'/billing/invoices/{i.id}',
            'when': i.issued_at,
            'key': f'invoice_unpaid:{i.id}',
            'dismissible': True,
        })

    # Failed messages — keyed by day, so it re-fires tomorrow.
    failed = (MessageLog.query
              .filter_by(org_id=org.id, status='failed')
              .filter(MessageLog.created_at >= now - timedelta(hours=24))
              .count())
    if failed >= FAILED_WARN_COUNT:
        items.append({
            'type': 'danger',
            'title': f'{failed} messages failed today',
            'body': 'Credits have been refunded automatically.',
            'url': '/reports/log?status=failed',
            'when': now,
            'key': f'failed_messages:{org.id}:{now.strftime("%Y%m%d")}',
            'dismissible': True,
        })

    return items


# --------------------------------------------------------------------------
# Master notifications
# --------------------------------------------------------------------------

def _for_master(user):
    from app.services import chat as chat_svc

    now = datetime.utcnow()
    items = []

    # Chat unread — not dismissible.
    chat_unread = chat_svc.total_unread(user)
    if chat_unread:
        items.append({
            'type': 'info',
            'title': f'{chat_unread} unread chat message'
                     f'{"s" if chat_unread != 1 else ""}',
            'body': 'Associates are waiting for a reply.',
            'url': '/chat/',
            'when': now,
            'key': None,
            'dismissible': False,
        })

    # Pending signups
    from app.services import signups as signup_svc
    pending_signups = signup_svc.pending_count()
    if pending_signups:
        items.append({
            'type': 'info',
            'title': f'{pending_signups} signup'
                     f'{"s" if pending_signups != 1 else ""} awaiting review',
            'body': 'Approve or reject from the signups page.',
            'url': '/master/signups',
            'when': now,
            'key': f'signups_pending:{pending_signups}',
            'dismissible': True,
        })
        
    # Unpaid invoices — one notification per invoice.
    unpaid = (Invoice.query
              .filter_by(status='unpaid')
              .order_by(Invoice.issued_at.desc())
              .limit(5).all())
    for i in unpaid:
        items.append({
            'type': 'info',
            'title': f'Invoice {i.number} unpaid',
            'body': f'{i.org.name} · {i.currency} {i.amount:,.0f}',
            'url': f'/master/invoices/{i.id}',
            'when': i.issued_at,
            'key': f'invoice_unpaid:{i.id}',
            'dismissible': True,
        })

    # Suspended orgs — key includes count so it re-fires when count changes.
    suspended = (Organization.query
                 .filter_by(status='suspended', is_master=False)
                 .all())
    if suspended:
        names = ', '.join(o.name for o in suspended[:3])
        extra = f' and {len(suspended) - 3} more' if len(suspended) > 3 else ''
        items.append({
            'type': 'warning',
            'title': f'{len(suspended)} associate'
                    f'{"s" if len(suspended) != 1 else ""} suspended',
            'body': f'{names}{extra}.',
            'url': '/master/orgs',
            'when': now,
            'key': f'suspended_orgs:{len(suspended)}',
            'dismissible': True,
        })

    # Queue backlog — key includes count bucket.
    queued = SendQueue.query.filter_by(status='pending').count()
    if queued >= 10:
        bucket = '10' if queued < 50 else '50' if queued < 200 else '200'
        items.append({
            'type': 'info',
            'title': f'{queued} jobs waiting in the send queue',
            'body': 'Check the worker is running.',
            'url': '/master/',
            'when': now,
            'key': f'queue_backlog:{bucket}',
            'dismissible': True,
        })

    return items