"""Nightly ledger reconciliation.

Run from cron:
    0 2 * * * cd /opt/roman-sms && ./venv/bin/python scripts/reconcile.py

Sends an alert email on drift, exits non-zero so cron mail also fires.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models import Organization, WalletTransaction
from app.services import mailer


def main():
    app = create_app()
    drifts = []

    with app.app_context():
        for org in Organization.query.order_by(Organization.id).all():
            total = (db.session.query(
                        db.func.coalesce(
                            db.func.sum(WalletTransaction.delta), 0))
                     .filter_by(org_id=org.id).scalar()) or 0
            last = (WalletTransaction.query
                    .filter_by(org_id=org.id)
                    .order_by(WalletTransaction.id.desc()).first())
            cached = last.balance_after if last else 0

            if int(total) != int(cached):
                drifts.append(
                    f'org={org.id} name={org.name!r} '
                    f'sum={int(total)} cached={int(cached)}')

        if drifts:
            body = ('Ledger drift detected:\n\n' +
                    '\n'.join(drifts) +
                    '\n\nInvestigate before taking any further action.')
            print(body)
            alert_to = app.config.get('ALERT_EMAIL')
            if alert_to:
                mailer.send(alert_to, '[Roman SMS] Ledger drift detected',
                            body)
        else:
            print('Reconciliation complete. 0 org(s) with drift.')

    sys.exit(1 if drifts else 0)


if __name__ == '__main__':
    main()