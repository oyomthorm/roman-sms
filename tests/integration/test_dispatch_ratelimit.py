import responses
from app.models import Campaign, MessageLog, SendQueue
from app.services import campaigns as c_svc
from app.services import dispatch
from tests.factories import ContactFactory, UserFactory


@responses.activate
def test_dispatch_respects_daily_limit(app, db, subscribed_associate, plan):
    """An org at its daily cap gets its job requeued, not sent."""
    plan.max_per_day = 1
    plan.max_per_minute = 100
    db.session.commit()

    responses.add(
        responses.POST, 'https://comms.egosms.co/api/v1/json/',
        json={'status': 'OK'}, status=200,
    )

    org = subscribed_associate
    user = UserFactory(org=org)

    # Pre-fill the daily counter
    from datetime import datetime
    db.session.add(MessageLog(
        org_id=org.id, phone='256700999999', body='x',
        status='sent', sent_at=datetime.utcnow()))
    db.session.commit()

    # New campaign with 1 recipient
    ContactFactory(org_id=org.id)
    campaign, _ = c_svc.create_campaign(
        org, name='T', body='Hi', created_by=user.id)

    ids = dispatch.claim_jobs()
    dispatch.process_job(ids[0])

    # Campaign back to queued, job back to pending, no HTTP call made
    db.session.refresh(campaign)
    assert campaign.status == 'queued'
    job = SendQueue.query.filter_by(campaign_id=campaign.id).first()
    assert job.status == 'pending'
    assert len(responses.calls) == 0