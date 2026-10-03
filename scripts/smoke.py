"""
Roman SMS smoke test.

Runs a full pipeline against the configured database and prints a
pass/fail report. Does NOT call the EgoSMS API — it stops short of the
worker send and inspects the queue instead.

    python scripts/smoke.py
    python scripts/smoke.py --cleanup

Exits non-zero on any failure, so it can gate a deploy.
"""
import argparse
import sys
from datetime import datetime, timedelta

from app import create_app
from app.extensions import db
from app.models import (Organization, User, Plan, Subscription, Contact,
                        Group, Campaign, MessageLog, SendQueue,
                        WalletTransaction)
from app.services import wallet as wallet_svc
from app.services import groups as groups_svc
from app.services import contacts as contacts_svc
from app.services import campaigns as campaigns_svc


SLUG = 'smoke-test-client'
EMAIL = 'smoke@testclient.local'
PASSWORD = 'smoke12345'


class Report:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.lines = []

    def check(self, label, condition, detail=''):
        if condition:
            self.passed += 1
            self.lines.append(f'  PASS  {label}')
        else:
            self.failed += 1
            self.lines.append(f'  FAIL  {label}  {detail}')

    def print(self):
        print('\n'.join(self.lines))
        total = self.passed + self.failed
        print(f'\n{self.passed}/{total} passed, {self.failed} failed.')


def cleanup_previous():
    org = Organization.query.filter_by(slug=SLUG).first()
    if not org:
        return
    MessageLog.query.filter_by(org_id=org.id).delete()
    SendQueue.query.filter_by(org_id=org.id).delete()
    Campaign.query.filter_by(org_id=org.id).delete()
    Contact.query.filter_by(org_id=org.id).delete()
    Group.query.filter_by(org_id=org.id).delete()
    WalletTransaction.query.filter_by(org_id=org.id).delete()
    Subscription.query.filter_by(org_id=org.id).delete()
    User.query.filter_by(email=EMAIL).delete()
    db.session.delete(org)
    db.session.commit()
    print(f'Cleaned previous smoke data for {SLUG}.')


def run():
    report = Report()
    print('Roman SMS smoke test\n' + '=' * 40)

    # ---- 1. Create org and admin
    master = Organization.query.filter_by(is_master=True).first()
    report.check('master org exists', master is not None)
    if not master:
        report.print()
        return report

    from app.services import orgs as orgs_svc
    try:
        org, admin = orgs_svc.create_associate(
            name='Smoke Test Client', slug=SLUG,
            brand_name='SMOKE', admin_email=EMAIL,
            admin_password=PASSWORD,
        )
        report.check('associate created', org.id is not None)
        report.check('admin linked to org', admin.org_id == org.id)
    except Exception as e:
        report.check('associate created', False, str(e))
        report.print()
        return report

    # ---- 2. Plan and wallet
    plan = Plan.query.filter_by(is_active=True).first()
    report.check('a plan exists', plan is not None)
    if not plan:
        report.print()
        return report

    sub = Subscription(
        org_id=org.id, plan_id=plan.id,
        starts_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=plan.validity_days),
        status='active', credits_granted=plan.credits,
    )
    db.session.add(sub)
    wallet_svc.credit(org.id, plan.credits, reason='plan_grant',
                      reference='smoke')
    db.session.commit()

    balance_after_plan = wallet_svc.get_balance(org.id)
    report.check('wallet credited', balance_after_plan == plan.credits,
                 f'got {balance_after_plan}, expected {plan.credits}')

    # ---- 3. Groups via import
    import io
    csv_bytes = (
        b"phone,name,group\n"
        b"0700010001,Alice,VIP\n"
        b"0700010002,Bob,VIP\n"
        b"0700010003,Carol,Other\n"
    )
    result = contacts_svc.import_csv(org, io.BytesIO(csv_bytes))
    report.check('import added 3 contacts', result['added'] == 3)
    report.check('import created 2 groups', result['groups_created'] == 2)

    vip = Group.query.filter_by(org_id=org.id, name='VIP').first()
    report.check('VIP group exists', vip is not None)
    report.check('VIP has 2 contacts',
                 vip and vip.contacts.count() == 2)

    # ---- 4. Create campaign targeted at VIP
    starting = wallet_svc.get_balance(org.id)
    campaign, segs = campaigns_svc.create_campaign(
        org, name='Smoke campaign', body='Hi {{name}}',
        group_id=vip.id, group_name='VIP',
        created_by=admin.id,
    )
    report.check('campaign queued', campaign.status == 'queued')
    report.check('campaign has 2 recipients', campaign.total == 2)
    report.check('credits debited',
                 wallet_svc.get_balance(org.id) == starting - segs,
                 f'{starting} -> {wallet_svc.get_balance(org.id)}')

    # ---- 5. Queue and messages
    jobs = SendQueue.query.filter_by(campaign_id=campaign.id).all()
    logs = MessageLog.query.filter_by(campaign_id=campaign.id).all()
    report.check('one queue row', len(jobs) == 1)
    report.check('two message logs', len(logs) == 2)
    report.check('all messages pending',
                 all(m.status == 'pending' for m in logs))
    report.check('brand prefix in body',
                 all('SMOKE: ' in m.body for m in logs))

    # ---- 6. Ledger invariant
    total = (db.session.query(
                db.func.coalesce(db.func.sum(WalletTransaction.delta), 0))
             .filter_by(org_id=org.id).scalar()) or 0
    last = (WalletTransaction.query
            .filter_by(org_id=org.id)
            .order_by(WalletTransaction.id.desc())
            .first())
    report.check('ledger invariant holds',
                 int(total) == int(last.balance_after),
                 f'sum={total} cached={last.balance_after}')

    # ---- 7. Opt-out enforced platform-wide
    from app.models import OptOut
    first_contact = Contact.query.filter_by(org_id=org.id).first()
    db.session.add(OptOut(phone=first_contact.phone, reason='smoke'))
    db.session.commit()

    recipients = campaigns_svc.resolve_recipients(org.id, group_id=vip.id)
    report.check('opt-out excluded from resolve',
                 first_contact.phone not in [c.phone for c in recipients])

    report.print()
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cleanup', action='store_true',
                        help='Remove smoke data after the run')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        cleanup_previous()
        report = run()
        if args.cleanup:
            cleanup_previous()
            print('Cleaned up.')
        sys.exit(1 if report.failed else 0)


if __name__ == '__main__':
    main()