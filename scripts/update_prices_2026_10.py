"""
Update plan pricing to the October 2026 schedule.

Old rates (post 0.7.1): Starter 50, Growth 45, Business 40, Scale 35.
New rates:              Starter 45, Growth 40, Business 35, Scale 30.

Also moves to one-time purchase semantics. Credits never expire:
`validity_days = 36500` (100 years) is the perpetual sentinel. The
display layer shows "No expiry" for anything >= 36500.

Usage:
    python scripts/update_prices_2026_10.py             # dry run (safe)
    python scripts/update_prices_2026_10.py --apply     # commit

Idempotent: running twice produces the same end state.
"""
import argparse
import sys
from pathlib import Path

# Allow running from the project root or from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.extensions import db
from app.models import Plan


PERPETUAL_DAYS = 36500  # 100 years — the "no expiry" sentinel


NEW_PLANS = [
    dict(name='Starter',  credits=1_000,   rate=45,
         tier_min=1,        tier_max=10_000,
         sort_order=1, max_contacts=5_000,
         max_per_minute=30, max_per_day=2_000),

    dict(name='Growth',   credits=10_000,  rate=40,
         tier_min=10_001,   tier_max=100_000,
         sort_order=2, max_contacts=50_000,
         max_per_minute=60, max_per_day=5_000),

    dict(name='Business', credits=100_000, rate=35,
         tier_min=100_001,  tier_max=300_000,
         sort_order=3, max_contacts=500_000,
         max_per_minute=120, max_per_day=10_000),

    dict(name='Scale',    credits=300_000, rate=30,
         tier_min=300_001,  tier_max=600_000,
         sort_order=4, max_contacts=None,
         max_per_minute=240, max_per_day=20_000),
]


def _plan_matches(plan, spec):
    """True if the plan already has the target values."""
    expected_price = spec['credits'] * spec['rate']
    try:
        current_price = int(plan.price)
    except (TypeError, ValueError):
        return False
    return (plan.is_active
            and plan.credits == spec['credits']
            and current_price == expected_price
            and plan.tier_min == spec['tier_min']
            and plan.tier_max == spec['tier_max']
            and plan.validity_days == PERPETUAL_DAYS)


def _print_plan(plan):
    rate = plan.rate_per_sms
    rate_s = f'{rate:.0f}' if rate else '?'
    try:
        price_s = f'{int(plan.price):,}'
    except (TypeError, ValueError):
        price_s = '?'
    tag = ' [inactive]' if not plan.is_active else ''
    print(f'  #{plan.id:<4} {plan.name:<14} '
          f'{plan.credits:>8,} cr @ UGX {rate_s:>3}/SMS  '
          f'price UGX {price_s:>14}{tag}')


def main(apply=False):
    app = create_app()
    with app.app_context():
        print()
        print('=' * 78)
        print('Plan pricing update — October 2026')
        print('=' * 78)
        print()

        # ---- Current state ----
        print('Currently active plans:')
        active = (Plan.query
                  .filter_by(is_active=True)
                  .order_by(Plan.sort_order, Plan.id)
                  .all())
        if not active:
            print('  (none)')
        for p in active:
            _print_plan(p)
        print()

        # ---- Target state ----
        print('Target plans:')
        for spec in NEW_PLANS:
            price = spec['credits'] * spec['rate']
            band = (f'{spec["tier_min"]:,}–'
                    f'{spec["tier_max"]:,}' if spec['tier_max']
                    else f'{spec["tier_min"]:,}+')
            print(f'  {spec["name"]:<14} '
                  f'{spec["credits"]:>8,} cr @ UGX {spec["rate"]:>3}/SMS  '
                  f'price UGX {price:>14,}  band {band}')
        print()

        # ---- Compute and apply changes ----
        deactivations = 0
        creations = 0

        for spec in NEW_PLANS:
            matching = next(
                (p for p in Plan.query.filter_by(
                    name=spec['name'], is_active=True).all()
                 if _plan_matches(p, spec)),
                None,
            )
            if matching:
                print(f'{spec["name"]}: already at target '
                      f'(id={matching.id}), skipping')
                continue

            # Deactivate any active plan with the same name
            old_actives = (Plan.query
                           .filter_by(name=spec['name'], is_active=True)
                           .all())
            for old in old_actives:
                try:
                    old_price = int(old.price)
                except (TypeError, ValueError):
                    old_price = '?'
                print(f'{spec["name"]}: deactivating old plan '
                      f'id={old.id} (UGX {old_price}, {old.credits} cr)')
                if apply:
                    old.is_active = False
                deactivations += 1

            # Create the new plan
            price = spec['credits'] * spec['rate']
            new_plan = Plan(
                name=spec['name'],
                price=price,
                currency='UGX',
                credits=spec['credits'],
                tier_min=spec['tier_min'],
                tier_max=spec['tier_max'],
                sort_order=spec['sort_order'],
                is_active=True,
                validity_days=PERPETUAL_DAYS,
                max_contacts=spec['max_contacts'],
                max_per_minute=spec['max_per_minute'],
                max_per_day=spec['max_per_day'],
            )
            print(f'{spec["name"]}: creating new plan '
                  f'(UGX {price:,}, {spec["credits"]:,} cr, '
                  f'validity=perpetual)')
            if apply:
                db.session.add(new_plan)
            creations += 1

        print()

        if apply:
            db.session.commit()
            print(f'Committed. '
                  f'{deactivations} deactivation(s), '
                  f'{creations} creation(s).')
        else:
            print(f'DRY RUN. '
                  f'{deactivations} deactivation(s), '
                  f'{creations} creation(s) would be applied.')
            print('Re-run with --apply to commit.')
        print()

        if apply:
            print('New active plans:')
            final = (Plan.query
                     .filter_by(is_active=True)
                     .order_by(Plan.sort_order, Plan.id)
                     .all())
            for p in final:
                _print_plan(p)
            print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Update plan pricing to the October 2026 schedule.')
    parser.add_argument('--apply', action='store_true',
                        help='Actually apply changes. Default is dry-run.')
    args = parser.parse_args()
    main(apply=args.apply)