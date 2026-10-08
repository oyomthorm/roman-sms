"""
Nightly wallet reconciliation.

Checks two invariants:

  1. Per org: SUM(delta) == last.balance_after
  2. Every credit row that isn't tagged as an external source must
     have a source_org_id, and that org must have a matching debit
     with the same reference.

Exits 0 when both hold. Exits 1 when either breaks, with a printed
report. Emails ALERT_EMAIL on failure.

Run manually:
    python scripts/reconcile.py

Run nightly via cron (per docs/DEPLOY.md):
    15 3 * * * cd /opt/roman-sms && venv/bin/python scripts/reconcile.py \\
              >> /var/log/roman-sms/cron.log 2>&1
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.extensions import db
from app.models import (Organization, WalletTransaction, MessageLog)
from app.services import wallet as wallet_svc
from app.services import mailer


def check_per_org_balance():
    """
    For every org: SUM(delta) must equal the cached balance_after on
    the latest WalletTransaction row.

    Returns a list of drift reports, one per org with a mismatch.
    """
    drifts = []

    for org in Organization.query.order_by(Organization.id).all():
        total = int((db.session.query(
                        db.func.coalesce(
                            db.func.sum(WalletTransaction.delta), 0))
                     .filter_by(org_id=org.id).scalar()) or 0)

        last = (WalletTransaction.query
                .filter_by(org_id=org.id)
                .order_by(WalletTransaction.id.desc())
                .first())
        cached = last.balance_after if last else 0

        if total != cached:
            drifts.append({
                'org_id': org.id,
                'org_name': org.name,
                'org_slug': org.slug,
                'sum': total,
                'cached': cached,
                'last_tx_id': last.id if last else None,
            })

    return drifts


def check_credit_sources():
    """
    Every credit row that isn't tagged as an external source must have
    a source_org_id, and that org must have a matching debit with the
    same reference.

    Returns a list of orphan credit rows.
    """
    from app.services.wallet import EXTERNAL_CREDIT_REASONS

    credits = (WalletTransaction.query
               .filter(WalletTransaction.delta > 0)
               .filter(~WalletTransaction.reason.in_(
                   list(EXTERNAL_CREDIT_REASONS)))
               .all())

    orphans = []
    for c in credits:
        if not c.source_org_id:
            orphans.append({
                'tx_id': c.id,
                'org_id': c.org_id,
                'delta': c.delta,
                'reason': c.reason,
                'reference': c.reference,
                'source_org_id': None,
                'problem': 'no source_org_id',
            })
            continue

        match = (WalletTransaction.query
                 .filter(WalletTransaction.org_id == c.source_org_id)
                 .filter(WalletTransaction.delta == -c.delta)
                 .filter(WalletTransaction.reference == c.reference)
                 .first())
        if not match:
            orphans.append({
                'tx_id': c.id,
                'org_id': c.org_id,
                'delta': c.delta,
                'reason': c.reason,
                'reference': c.reference,
                'source_org_id': c.source_org_id,
                'problem': 'no matching debit',
            })

    return orphans


def send_alert(subject, body):
    """Send to ALERT_EMAIL if configured. Never raises."""
    try:
        app_alert = None
        from flask import current_app
        app_alert = current_app.config.get('ALERT_EMAIL')
        if not app_alert:
            print('  (no ALERT_EMAIL configured; alert not sent)')
            return
        mailer.send(to=app_alert, subject=subject, body_text=body)
        print(f'  Alert sent to {app_alert}')
    except Exception as e:
        print(f'  Alert send failed: {e}')


def main():
    app = create_app()
    with app.app_context():
        print('=' * 60)
        print('Reconciliation')
        print('=' * 60)

        drift_failures = False
        source_failures = False

        # ---- Check 1: per-org balance invariant ----
        drifts = check_per_org_balance()
        if drifts:
            drift_failures = True
            print()
            print(f'DRIFT: {len(drifts)} org(s) with SUM(delta) '
                  f'!= last.balance_after')
            for d in drifts:
                print(f'  org {d["org_id"]} ({d["org_slug"]}): '
                      f'sum={d["sum"]:,} cached={d["cached"]:,} '
                      f'last_tx={d["last_tx_id"]}')
        else:
            n = Organization.query.count()
            print(f'[OK] Per-org balance: {n} org(s) checked, '
                  f'0 with drift')

        # ---- Check 2: credit sources ----
        orphans = check_credit_sources()
        if orphans:
            source_failures = True
            print()
            print(f'ORPHANS: {len(orphans)} credit row(s) without a '
                  f'matching source debit')
            for o in orphans[:20]:
                print(f'  tx {o["tx_id"]} org={o["org_id"]} '
                      f'delta={o["delta"]:+,} reason={o["reason"]} '
                      f'ref={o["reference"]} '
                      f'source={o["source_org_id"]} — {o["problem"]}')
            if len(orphans) > 20:
                print(f'  ... and {len(orphans) - 20} more')
        else:
            print('[OK] Credit sources: every internal credit has a '
                  'matching debit')

        print()

        # ---- Result ----
        if drift_failures or source_failures:
            print('RESULT: FAILED')
            body_lines = ['Reconciliation found problems.', '']
            if drift_failures:
                body_lines.append(f'{len(drifts)} org(s) with '
                                  f'balance drift:')
                for d in drifts:
                    body_lines.append(
                        f'  {d["org_slug"]}: '
                        f'sum={d["sum"]:,} cached={d["cached"]:,}'
                    )
                body_lines.append('')
            if source_failures:
                body_lines.append(
                    f'{len(orphans)} orphan credit row(s):')
                for o in orphans[:20]:
                    body_lines.append(
                        f'  tx {o["tx_id"]} org={o["org_id"]} '
                        f'delta={o["delta"]:+,} '
                        f'reason={o["reason"]} — {o["problem"]}'
                    )
            send_alert('Roman SMS: reconciliation failed',
                       '\n'.join(body_lines))
            sys.exit(1)

        print('RESULT: PASSED')
        sys.exit(0)


if __name__ == '__main__':
    main()