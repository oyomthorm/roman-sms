"""
Subscription service. Granting a plan does two things atomically:
  1. creates a Subscription row
  2. credits the wallet with plan.credits

Any existing active subscription is expired first so only one is active
per org at a time.
"""
from datetime import datetime, timedelta
from app.extensions import db
from app.models import Subscription
from app.services import wallet as wallet_svc
from app.services.audit import log as audit


class SubscriptionError(Exception):
    pass


def current_for(org_id):
    return (Subscription.query
            .filter_by(org_id=org_id, status='active')
            .filter(Subscription.expires_at > datetime.utcnow())
            .order_by(Subscription.id.desc())
            .first())


def history_for(org_id, limit=20):
    return (Subscription.query
            .filter_by(org_id=org_id)
            .order_by(Subscription.id.desc())
            .limit(limit)
            .all())


def grant(org, plan, *, duration_days=None, actor_id=None,
          credit_wallet=True, note=None):
    """
    Create a new subscription for org under plan.
    Expires any existing active subscription.
    Credits plan.credits to the wallet unless credit_wallet=False.
    """
    if not org or not plan:
        raise SubscriptionError('Org and plan are required.')

    duration = int(duration_days or plan.validity_days or 30)
    if duration <= 0:
        raise SubscriptionError('Duration must be positive.')

    # Expire current active subs (mark them expired, keep history).
    now = datetime.utcnow()
    (Subscription.query
     .filter_by(org_id=org.id, status='active')
     .update({'status': 'expired'}, synchronize_session=False))

    sub = Subscription(
        org_id=org.id, plan_id=plan.id,
        starts_at=now,
        expires_at=now + timedelta(days=duration),
        status='active',
        credits_granted=plan.credits if credit_wallet else 0,
    )
    db.session.add(sub)
    db.session.flush()

    if credit_wallet and plan.credits > 0:
        master_id = wallet_svc.master_org_id()
        wallet_svc.transfer(
            master_id, org.id, plan.credits,
            reason='plan_grant',
            reference=f'subscription:{sub.id}',
            note=note or f'{plan.name} plan ({duration} days)',
            actor_id=actor_id,
        )

    db.session.commit()
    audit('subscription_grant',
          f'org={org.slug} plan={plan.name} days={duration} '
          f'credits={plan.credits if credit_wallet else 0}',
          org_id=org.id, actor_id=actor_id)
    return sub