import responses
from datetime import datetime, timedelta
from app.models import Campaign, MessageLog, SendQueue, Organization
from app.services import campaigns as c_svc
from app.services import dispatch
from app.services import wallet as wallet_svc
from tests.factories import ContactFactory, UserFactory


@responses.activate
def test_dispatch_sends_and_completes(app, db, subscribed_associate):
    responses.add(
        responses.POST, 'https://comms.egosms.co/api/v1/json/',
        json={'status': 'OK'}, status=200,
    )
    org = subscribed_associate
    user = UserFactory(org=org)
    for _ in range(3):
        ContactFactory(org_id=org.id)

    starting = wallet_svc.get_balance(org.id)
    campaign, _ = c_svc.create_campaign(
        org, name='T', body='Hi', created_by=user.id)

    ids = dispatch.claim_jobs()
    assert len(ids) == 1
    dispatch.process_job(ids[0])

    db.session.refresh(campaign)
    assert campaign.status == 'complete'
    assert campaign.sent_count == 3
    assert campaign.failed_count == 0
    assert wallet_svc.get_balance(org.id) == starting - 3

    logs = MessageLog.query.filter_by(campaign_id=campaign.id).all()
    assert all(m.status == 'sent' for m in logs)


@responses.activate
def test_dispatch_refunds_on_api_error(app, db, subscribed_associate):
    responses.add(
        responses.POST, 'https://comms.egosms.co/api/v1/json/',
        json={'error': 'insufficient balance'}, status=200,
    )
    org = subscribed_associate
    user = UserFactory(org=org)
    for _ in range(2):
        ContactFactory(org_id=org.id)

    starting = wallet_svc.get_balance(org.id)
    campaign, _ = c_svc.create_campaign(
        org, name='T', body='Hi', created_by=user.id)
    # After debit
    assert wallet_svc.get_balance(org.id) == starting - 2

    ids = dispatch.claim_jobs()
    dispatch.process_job(ids[0])

    db.session.refresh(campaign)
    assert campaign.status == 'complete'
    assert campaign.sent_count == 0
    assert campaign.failed_count == 2
    # Refund restores balance
    assert wallet_svc.get_balance(org.id) == starting

    from app.models import WalletTransaction
    refunds = (WalletTransaction.query
               .filter_by(org_id=org.id, reason='refund').all())
    assert sum(r.delta for r in refunds) == 2


@responses.activate
def test_dispatch_cancels_for_suspended_org(app, db, subscribed_associate):
    responses.add(
        responses.POST, 'https://comms.egosms.co/api/v1/json/',
        json={'status': 'OK'}, status=200,
    )
    org = subscribed_associate
    user = UserFactory(org=org)
    ContactFactory(org_id=org.id)

    campaign, _ = c_svc.create_campaign(
        org, name='T', body='Hi', created_by=user.id)

    # Suspend before the worker runs
    org.status = 'suspended'
    db.session.commit()

    ids = dispatch.claim_jobs()
    dispatch.process_job(ids[0])

    db.session.refresh(campaign)
    assert campaign.status == 'cancelled'
    # No HTTP call made
    assert len(responses.calls) == 0


def test_requeue_stuck_jobs(app, db, subscribed_associate):
    org = subscribed_associate
    user = UserFactory(org=org)
    ContactFactory(org_id=org.id)
    campaign, _ = c_svc.create_campaign(
        org, name='T', body='Hi', created_by=user.id)

    job = SendQueue.query.filter_by(campaign_id=campaign.id).first()
    job.status = 'processing'
    job.locked_at = datetime.utcnow() - timedelta(minutes=30)
    db.session.commit()

    requeued = dispatch.requeue_stuck(max_age_minutes=15)
    assert requeued == 1
    db.session.refresh(job)
    assert job.status == 'pending'