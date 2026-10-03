"""Bootstrap the platform.

Creates:
  - The master org (Roman SMS itself)
  - A master admin user
  - The system org (internal sending identity, "Roman SMS Platform")
  - Four tier plans for pay-as-you-go pricing

Idempotent — safe to re-run. Nothing is duplicated or overwritten.

Run once after `flask db upgrade`:
    python scripts/seed.py
"""
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

MASTER_OPENING_CREDITS = 100000
SYSTEM_OPENING_CREDITS = 100000


# ----------------------------------------------------------------------
# Tier plans.
#
# Rate per SMS decreases as the top-up grows. Wholesale from Pahappa is
# 35 / 30 / 25 / 20 UGX depending on volume — retail rates below sit
# above those with margin built in.
# ----------------------------------------------------------------------
STARTER_PLANS = [
    dict(
        name='Starter',
        sort_order=10,
        tier_min=1,
        tier_max=1_000,
        price=50_000,
        credits=1_000,
        max_contacts=1_000,
        max_per_minute=30,
        max_per_day=2_000,
        is_featured=False,
    ),
    dict(
        name='Growth',
        sort_order=20,
        tier_min=1_001,
        tier_max=10_000,
        price=450_000,
        credits=10_000,
        max_contacts=10_000,
        max_per_minute=60,
        max_per_day=10_000,
        is_featured=True,
    ),
    dict(
        name='Business',
        sort_order=30,
        tier_min=10_001,
        tier_max=50_000,
        price=2_000_000,
        credits=50_000,
        max_contacts=50_000,
        max_per_minute=120,
        max_per_day=30_000,
        is_featured=False,
    ),
    dict(
        name='Scale',
        sort_order=40,
        tier_min=50_001,
        tier_max=200_000,
        price=7_000_000,
        credits=200_000,
        max_contacts=200_000,
        max_per_minute=240,
        max_per_day=100_000,
        is_featured=False,
    ),
]

def main():
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
        # ----------------------------------------------------------
        if wallet_svc.get_balance(master.id) == 0:
            wallet_svc.credit(
                master.id,
                MASTER_OPENING_CREDITS,
                reason='master_opening_balance',
                note='Platform operating budget',
                actor_id=admin.id,
            )
            print(f'Granted {MASTER_OPENING_CREDITS:,} credits to master org.')
        else:
            print(f'Master wallet already funded: '
                  f'{wallet_svc.get_balance(master.id):,}')

        # ----------------------------------------------------------
        # 4. System org — internal sending identity
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

            wallet_svc.credit(
                platform.id,
                SYSTEM_OPENING_CREDITS,
                reason='master_opening_balance',
                note='Platform sending budget',
                actor_id=admin.id,
            )
            print(f'Granted {SYSTEM_OPENING_CREDITS:,} credits to system org.')
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
                    validity_days=None,   # no expiry
                ))
            print(f'Seeded {len(STARTER_PLANS)} tier plans.')
        else:
            print('Plans already present.')

        db.session.commit()

        print()
        print('=' * 50)
        print('Seed complete.')
        print(f'Login: {master_email} / {master_password}')
        print('=' * 50)


if __name__ == '__main__':
    main()