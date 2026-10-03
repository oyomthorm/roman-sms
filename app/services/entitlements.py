from datetime import datetime
from app.models import Contact, Subscription
from app.services.wallet import get_balance


class EntitlementError(Exception):
    """Raised when an org is not allowed to perform an action."""


DEFAULT_RATE_UGX = 50.0   # fallback when no plan is active


def active_subscription(org_id):
    now = datetime.utcnow()
    return (Subscription.query
            .filter_by(org_id=org_id, status='active')
            .filter(Subscription.expires_at > now)
            .order_by(Subscription.id.desc())
            .first())


def current_rate_ugx(org_id):
    """
    Value of one credit, in UGX, for this org.

    Uses the active plan's derived rate. Falls back to DEFAULT_RATE_UGX
    when there is no active plan (new accounts, expired accounts).
    """
    sub = active_subscription(org_id)
    if sub and sub.plan and sub.plan.rate_per_sms:
        return float(sub.plan.rate_per_sms)
    return DEFAULT_RATE_UGX


def balance_value_ugx(org_id):
    """Current balance, in UGX."""
    return get_balance(org_id) * current_rate_ugx(org_id)


def check_can_send(org, count):
    """Raises EntitlementError or returns the active subscription."""
    if org.status != 'active':
        raise EntitlementError('Account suspended. Contact Roman SMS support.')

    sub = active_subscription(org.id)
    if not sub:
        raise EntitlementError('No active plan. Please purchase a plan.')

    balance = get_balance(org.id)
    if balance < count:
        rate = current_rate_ugx(org.id)
        raise EntitlementError(
            f'Insufficient credit. Need {count} SMS '
            f'(≈ UGX {count * rate:,.0f}), '
            f'you have {balance} SMS (≈ UGX {balance * rate:,.0f}).'
        )
    return sub


def check_contact_limit(org, incoming=1):
    sub = active_subscription(org.id)
    if not sub or not sub.plan.max_contacts:
        return
    current = Contact.query.filter_by(org_id=org.id).count()
    if current + incoming > sub.plan.max_contacts:
        raise EntitlementError(
            f'Contact limit reached ({sub.plan.max_contacts}). Upgrade your plan.'
        )