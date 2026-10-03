"""
Plan service.

Plans are pay-as-you-go tiers. Each tier has a range of top-up sizes
(`tier_min` to `tier_max`), a fixed price, and a fixed number of credits.
The derived rate per SMS decreases as the tier grows.

Sorting is by `sort_order` (lower first), then tier_min, then price.
"""
from app.extensions import db
from app.models import Plan
from app.services.audit import log as audit


class PlanError(Exception):
    pass


# ----------------------------------------------------------------------
# Reads
# ----------------------------------------------------------------------

def list_all():
    """Every plan, active or not. Used by the master plan list."""
    return (Plan.query
            .order_by(Plan.sort_order.asc(),
                      Plan.tier_min.asc().nullslast(),
                      Plan.price.asc())
            .all())


def list_active():
    """Active plans, in tier order."""
    return (Plan.query
            .filter_by(is_active=True)
            .order_by(Plan.sort_order.asc(),
                      Plan.tier_min.asc().nullslast(),
                      Plan.price.asc())
            .all())


def list_for_pricing():
    """
    Alias of list_active, named for what it is used for — the pricing
    table on the landing page and the associate plans page.
    """
    return list_active()


def get_featured():
    """
    The plan marked is_featured, or the middle one as a fallback.
    Used to highlight the 'best value' row in the pricing table.
    """
    featured = (Plan.query
                .filter_by(is_active=True, is_featured=True)
                .order_by(Plan.sort_order.asc())
                .first())
    if featured:
        return featured
    plans = list_active()
    if not plans:
        return None
    return plans[len(plans) // 2]


def get(plan_id):
    return db.session.get(Plan, plan_id)


# ----------------------------------------------------------------------
# Validation helpers
# ----------------------------------------------------------------------

def _int_or_none(value):
    if value in (None, '', 'None'):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise PlanError('Tier bounds must be numbers or blank.')


def _validate_tier(name, tier_min, tier_max):
    if tier_min is not None and tier_max is not None:
        if tier_min > tier_max:
            raise PlanError(
                f'{name}: tier minimum cannot exceed the maximum.'
            )
    return tier_min, tier_max


# ----------------------------------------------------------------------
# Create / update
# ----------------------------------------------------------------------

def create_plan(*, name, price, currency='UGX', credits,
                validity_days=None, max_contacts=None,
                max_per_minute=60, max_per_day=5000,
                tier_min=None, tier_max=None,
                sort_order=0, is_featured=False,
                actor_id=None):
    name = (name or '').strip()
    if not name:
        raise PlanError('Plan name is required.')

    try:
        price = float(price)
        credits = int(credits)
        max_per_minute = int(max_per_minute)
        max_per_day = int(max_per_day)
        max_contacts = (int(max_contacts)
                        if max_contacts not in (None, '') else None)
        validity_days = (int(validity_days)
                         if validity_days not in (None, '') else None)
        sort_order = int(sort_order or 0)
    except (TypeError, ValueError):
        raise PlanError('Price, credits, and limits must be numbers.')

    if price <= 0:
        raise PlanError('Price must be positive.')
    if credits <= 0:
        raise PlanError('Credits must be positive.')

    tier_min = _int_or_none(tier_min)
    tier_max = _int_or_none(tier_max)
    tier_min, tier_max = _validate_tier(name, tier_min, tier_max)

    plan = Plan(
        name=name, price=price, currency=currency.upper(),
        credits=credits,
        validity_days=validity_days,
        max_contacts=max_contacts,
        max_per_minute=max_per_minute,
        max_per_day=max_per_day,
        tier_min=tier_min,
        tier_max=tier_max,
        sort_order=sort_order,
        is_featured=is_featured,
        is_active=True,
    )
    db.session.add(plan)
    db.session.commit()
    audit('plan_create',
          f'name={plan.name} price={price} credits={credits} '
          f'tier={tier_min}-{tier_max}',
          actor_id=actor_id)
    return plan


def update_plan(plan, *, name, price, currency, credits,
                validity_days=None, max_contacts=None,
                max_per_minute=60, max_per_day=5000,
                tier_min=None, tier_max=None,
                sort_order=0, is_featured=False,
                actor_id=None):
    if not plan:
        raise PlanError('Plan not found.')

    name = (name or '').strip()
    if not name:
        raise PlanError('Plan name is required.')

    try:
        plan.price = float(price)
        plan.credits = int(credits)
        plan.max_per_minute = int(max_per_minute)
        plan.max_per_day = int(max_per_day)
        plan.max_contacts = (int(max_contacts)
                             if max_contacts not in (None, '') else None)
        plan.validity_days = (int(validity_days)
                              if validity_days not in (None, '') else None)
        plan.sort_order = int(sort_order or 0)
    except (TypeError, ValueError):
        raise PlanError('Price, credits, and limits must be numbers.')

    if plan.price <= 0 or plan.credits <= 0:
        raise PlanError('Price and credits must be positive.')

    tier_min = _int_or_none(tier_min)
    tier_max = _int_or_none(tier_max)
    tier_min, tier_max = _validate_tier(name, tier_min, tier_max)

    plan.name = name
    plan.currency = (currency or 'UGX').upper()
    plan.tier_min = tier_min
    plan.tier_max = tier_max
    plan.is_featured = is_featured

    db.session.commit()
    audit('plan_update', f'id={plan.id} name={plan.name}', actor_id=actor_id)
    return plan


def toggle_active(plan, *, actor_id=None):
    if not plan:
        raise PlanError('Plan not found.')
    plan.is_active = not plan.is_active
    db.session.commit()
    audit('plan_toggle',
          f'id={plan.id} active={plan.is_active}', actor_id=actor_id)
    return plan