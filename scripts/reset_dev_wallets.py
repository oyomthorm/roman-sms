"""
One-off dev helper: zero the master and system wallets so the seed
can be re-run against a clean slate. Writes a compensating negative
adjustment per org — never deletes ledger rows (see ADR-001).

DO NOT RUN ON PRODUCTION.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models import Organization
from app.services import wallet as wallet_svc


def main():
    app = create_app()
    with app.app_context():
        for flag, label in [(True, 'master'), (None, 'system')]:
            if flag is True:
                org = Organization.query.filter_by(is_master=True).first()
            else:
                org = Organization.query.filter_by(is_system=True).first()
            if not org:
                print(f'{label}: no org found, skipping')
                continue
            bal = wallet_svc.get_balance(org.id)
            if bal == 0:
                print(f'{label}: already at 0')
                continue
            wallet_svc.debit(
                org.id, bal,
                reason='dev_reset',
                note='Dev-only: zero for Pahappa sync test',
            )
            print(f'{label}: wrote -{bal:,} adjustment, balance now 0')
        db.session.commit()
        print()
        print('Now run: python scripts/seed.py')


if __name__ == '__main__':
    main()