"""Repro test for the last-run-doesn't-fire bug (#49).

A schedule with N times should produce N campaigns. If the last time is
due and claim_due_schedule marks the schedule 'completed' before
materialize_run sees it, the last campaign is silently skipped.
"""
import json
from datetime import datetime, timedelta

from app.extensions import db
from app.models import CampaignSchedule, Campaign
from app.services import schedules as sched_svc


def _make_due_schedule(db, org, name='Bug repro', one_time=True):
    """Create a schedule whose single time is already in the past."""
    local_now = datetime.utcnow() + timedelta(hours=3)
    past_local = (local_now - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
    schedule = CampaignSchedule(
        org_id=org.id,
        name=name,
        body='hello',
        sender_id=org.brand_name,
        scheduled_times=json.dumps([past_local]),
        status='active',
        next_run_at=datetime.utcnow() - timedelta(minutes=1),
    )
    db.session.add(schedule)
    db.session.commit()
    return schedule


def test_last_run_fires(db):
    """A schedule with one due time should fire one campaign."""
    from tests.factories import OrgFactory, ContactFactory

    org = OrgFactory()
    ContactFactory(org=org, phone='256700000001', name='X')
    schedule = _make_due_schedule(db, org)
    sid = schedule.id

    claim = sched_svc.claim_due_schedule()
    assert claim is not None, 'claim_due_schedule returned None'
    schedule_id, fired = claim
    assert schedule_id == sid

    sched_svc.materialize_run(schedule_id, fired_iso=fired)

    campaign = Campaign.query.filter_by(schedule_id=sid).first()
    assert campaign is not None, 'last run did not create a campaign'
    assert campaign.total == 1