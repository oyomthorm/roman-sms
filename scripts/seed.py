"""Bootstrap the platform.

Creates:
  - The master org (Roman SMS itself)
  - A master admin user
  - The system org (internal sending identity, "Roman SMS Platform")
  - Four tier plans for pay-as-you-go pricing

Idempotent — safe to re-run. Nothing is duplicated or overwritten.

Wallet funding:
  The master org's opening balance is fetched from Pahappa — it
  mirrors your real wholesale credit balance at seed time. This
  keeps the internal ledger honest: the master wallet shows what
  you actually have available to send.

  The system org starts at 0. The master funds it from its own
  wallet when pool campaigns need to send. This avoids double-
  counting credits, since Pahappa issues a single pool shared by
  both orgs (see ADR-002).

Run once after `flask db upgrade`:
    python scripts/seed.py

Skip the Pahappa balance query with:
    python scripts/seed.py --skip-balance
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models import Organization, User, Plan
from app.services import wallet as wallet_svc


MASTER_ORG_NAME = 'Roman SMS'
MASTER_ORG_SLUG = 'roman-sms'
MASTER_BRAND = 'Roman SMS'

SYSTEM_ORG_NAME = 'Roman SMS Platform'
SYSTEM_ORG_SLUG = 'roman-platform'
SYSTEM_BRAND = 'ROMANSMS'

# Fallback only used if the Pahappa API is unreachable and
# --skip-balance is not set. Zero is the honest default — the
# operator can fund the wallet later via `flask fund-master`.
MASTER_FALLBACK_CREDITS = 0


# Sentinel for "credits never expire". Any validity_days >= this value
# is rendered as "No expiry" in the UI. 100 years in days.
PERPETUAL_DAYS = 36500


# ----------------------------------------------------------------------
# Tier plans (October 2026 schedule).
#
# Every tier earns a flat UGX 10 margin per SMS against Pahappa's
# wholesale band for that volume. Retail bands match wholesale bands.
# Bundle sizes are fixed at the lower edge of each band, rounded to a
# practical number.
#
#   Starter   1,000 cr @ UGX 45/SMS = UGX 45,000   (wholesale 35, margin 10)
#   Growth   10,000 cr @ UGX 40/SMS = UGX 400,000  (wholesale 30, margin 10)
#   Business 100,000 cr @ UGX 35/SMS = UGX 3.5M    (wholesale 25, margin 10)
#   Scale    300,000 cr @ UGX 30/SMS = UGX 9.0M    (wholesale 20, margin 10)
#
# Enterprise (600,000+) has no Plan row — the master quotes it manually.
#
# Credits never expire: validity_days is set to PERPETUAL_DAYS so a
# subscription granted from any of these plans effectively never lapses.
# ----------------------------------------------------------------------
STARTER_PLANS = [
    dict(
        name='Starter',
        sort_order=10,
        tier_min=1,
        tier_max=10_000,
        price=45_000,
        credits=1_000,
        max_contacts=5_000,
        max_per_minute=30,
        max_per_day=2_000,
        is_featured=False,
    ),
    dict(
        name='Growth',
        sort_order=20,
        tier_min=10_001,
        tier_max=100_000,
        price=400_000,
        credits=10_000,
        max_contacts=50_000,
        max_per_minute=60,
        max_per_day=5_000,
        is_featured=True,
    ),
    dict(
        name='Business',
        sort_order=30,
        tier_min=100_001,
        tier_max=300_000,
        price=3_500_000,
        credits=100_000,
        max_contacts=500_000,
        max_per_minute=120,
        max_per_day=10_000,
        is_featured=False,
    ),
    dict(
        name='Scale',
        sort_order=40,
        tier_min=300_001,
        tier_max=600_000,
        price=9_000_000,
        credits=300_000,
        max_contacts=None,   # unlimited
        max_per_minute=240,
        max_per_day=20_000,
        is_featured=False,
    ),
]


# ----------------------------------------------------------------------
# Pahappa balance lookup
# ----------------------------------------------------------------------

def _fetch_pahappa_balance():
    """
    Query Pahappa for the current wholesale credit balance.

    Returns:
        int     — the balance, if the call succeeded
        None    — if the call failed or credentials are missing

    Never raises. The seed must be able to complete even when
    Pahappa's API is unreachable.
    """
    try:
        from app.services.egosms_client import EgoSMSClient
    except ImportError as e:
        print(f'  Could not import EgoSMS client: {e}')
        return None

    try:
        client = EgoSMSClient()
    except Exception as e:
        print(f'  Could not instantiate EgoSMS client: {e}')
        return None

    if not client.username:
        print('  EGOSMS_USERNAME is not configured. '
              'Skipping balance query.')
        return None

    print(f'  Querying Pahappa at {client.endpoint} '
          f'(sandbox={client.sandbox})...')

    try:
        resp = client.balance()
    except Exception as e:
        print(f'  Pahappa balance query raised: {e}')
        return None

    if not resp.ok:
        print(f'  Pahappa balance query failed: '
              f'{resp.message or "unknown error"}')
        return None

    if resp.balance is None:
        print('  Pahappa returned OK but no balance value.')
        return None

    return int(resp.balance)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main(skip_balance=False):
    app = create_app()
    with app.app_context():
        db.create_all()

        # ----------------------------------------------------------
        # 1. Master org
        # ----------------------------------------------------------
        master = Organization.query.filter_by(is_master=True).first()
        if not master:
            master = Organization(
                name=MASTER_ORG_NAME,
                slug=MASTER_ORG_SLUG,
                brand_name=MASTER_BRAND,
                status='active',
                is_master=True,
                is_system=False,
            )
            db.session.add(master)
            db.session.flush()
            print(f'Created master org id={master.id}')
        else:
            print(f'Master org exists id={master.id}')

        # ----------------------------------------------------------
        # 2. Master admin
        # ----------------------------------------------------------
        master_email = app.config.get('MASTER_EMAIL',
                                      'admin@romansms.local')
        master_password = app.config.get('MASTER_PASSWORD',
                                         'ChangeMe123!')

        admin = User.query.filter_by(email=master_email).first()
        if not admin:
            admin = User(
                email=master_email,
                full_name='Roman SMS Admin',
                role='master_admin',
                org_id=master.id,
            )
            admin.set_password(master_password)
            db.session.add(admin)
            db.session.flush()
            print(f'Created master admin {master_email}')
        else:
            print(f'Master admin {master_email} exists')

        # ----------------------------------------------------------
        # 3. Master operating wallet
        #
        # The master wallet mirrors our Pahappa wholesale balance.
        # We fetch it from the API so the internal ledger matches
        # reality. If the API is down, we leave the wallet at 0 and
        # tell the operator how to fund it manually.
        # ----------------------------------------------------------
        existing_master = wallet_svc.get_balance(master.id)

        if existing_master > 0:
            print(f'Master wallet already funded: {existing_master:,}')
        elif skip_balance:
            print('Master wallet left at 0 (--skip-balance).')
            print('  Run `flask fund-master <amount>` to set it.')
        else:
            print('Fetching master opening balance from Pahappa...')
            pahappa_balance = _fetch_pahappa_balance()

            if pahappa_balance is not None and pahappa_balance > 0:
                wallet_svc.credit(
                    master.id,
                    pahappa_balance,
                    reason='master_opening_balance',
                    note='Mirrors Pahappa wholesale balance at seed time',
                    actor_id=admin.id,
                )
                print(f'  Granted {pahappa_balance:,} credits to master org.')
            else:
                print(f'  Falling back to '
                      f'{MASTER_FALLBACK_CREDITS:,} credits.')
                if MASTER_FALLBACK_CREDITS > 0:
                    wallet_svc.credit(
                        master.id,
                        MASTER_FALLBACK_CREDITS,
                        reason='master_opening_balance',
                        note='Fallback — Pahappa balance unavailable',
                        actor_id=admin.id,
                    )
                else:
                    print('  Master wallet left at 0.')
                    print('  Run `flask fund-master <amount>` to set it '
                          'manually.')

        # ----------------------------------------------------------
        # 4. System org — internal sending identity
        #
        # Starts at 0. The master funds it from its own wallet when
        # pool campaigns need to send. This avoids double-counting:
        # Pahappa issues a single credit pool shared by both orgs.
        # ----------------------------------------------------------
        platform = Organization.query.filter_by(is_system=True).first()
        if not platform:
            platform = Organization(
                name=SYSTEM_ORG_NAME,
                slug=SYSTEM_ORG_SLUG,
                brand_name=SYSTEM_BRAND,
                status='active',
                is_master=False,
                is_system=True,
                parent_id=master.id,
            )
            db.session.add(platform)
            db.session.flush()
            print(f'Created system org id={platform.id}')

            print('  System org wallet starts at 0. Fund it from the '
                  'master console or via')
            print('  `flask fund-platform <amount>` when pool campaigns '
                  'need to send.')
        else:
            print(f'System org exists id={platform.id}')

        # ----------------------------------------------------------
        # 5. Tier plans
        # ----------------------------------------------------------
        if not Plan.query.first():
            for spec in STARTER_PLANS:
                db.session.add(Plan(
                    name=spec['name'],
                    sort_order=spec['sort_order'],
                    tier_min=spec['tier_min'],
                    tier_max=spec['tier_max'],
                    price=spec['price'],
                    credits=spec['credits'],
                    currency='UGX',
                    max_contacts=spec['max_contacts'],
                    max_per_minute=spec['max_per_minute'],
                    max_per_day=spec['max_per_day'],
                    is_featured=spec['is_featured'],
                    is_active=True,
                    validity_days=PERPETUAL_DAYS,
                ))
            print(f'Seeded {len(STARTER_PLANS)} tier plans.')

            print()
            print('  ' + '-' * 70)
            print(f'  {"Plan":<10} {"Bundle":>10} {"Band":>20} '
                  f'{"Rate":>6} {"Price":>14}')
            print('  ' + '-' * 70)
            for spec in STARTER_PLANS:
                rate = spec['price'] // spec['credits']
                band = f'{spec["tier_min"]:,}–{spec["tier_max"]:,}'
                print(f'  {spec["name"]:<10} '
                      f'{spec["credits"]:>10,} '
                      f'{band:>20} '
                      f'UGX {rate:>3} '
                      f'{spec["price"]:>14,}')
            print('  ' + '-' * 70)
        else:
            print('Plans already present. Run '
                  'scripts/update_prices_2026_10.py to reprice.')

        db.session.commit()

        # ----------------------------------------------------------
        # Summary
        # ----------------------------------------------------------
        print()
        print('=' * 60)
        print('Seed complete.')
        print(f'Master login:  {master_email} / {master_password}')
        print(f'Master wallet: {wallet_svc.get_balance(master.id):,} '
              f'credits')
        print(f'System wallet: {wallet_svc.get_balance(platform.id):,} '
              f'credits')
        print('=' * 60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Bootstrap the platform.')
    parser.add_argument(
        '--skip-balance', action='store_true',
        help='Do not query Pahappa for the opening master balance.')
    args = parser.parse_args()
    main(skip_balance=args.skip_balance)