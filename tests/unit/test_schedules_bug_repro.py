"""Repro tests for the last-run-doesn't-fire bug (#49).

A schedule with N times should produce N campaigns. Before the fix,
claim_due_schedule marked the schedule 'completed' before
materialize_run saw it, so the last (and only, for single-time schedules)
run was silently skipped.

Uses subscribed_associate so check_can_send passes: the org has an active
subscription and a funded wallet. Without that, materialize_run bails at
check_can_send and no campaign is created regardless of #49.
"""
import json
from datetime import datetime, timedelta

from app.extensions import db
from app.models import CampaignSchedule, Campaign
from app.services import schedules as sched_svc


def _make_due_schedule(db, org, name='Bug repro'):
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


def test_last_run_fires(db, master_org, subscribed_associate):
    """A schedule with one due time should fire one campaign."""
    from tests.factories import ContactFactory

    org = subscribed_associate
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


def test_multi_time_schedule_fires_all(db, master_org, subscribed_associate):
    """A schedule with 3 due times should fire 3 campaigns."""
    from tests.factories import ContactFactory

    org = subscribed_associate
    ContactFactory(org=org, phone='256700000002', name='Y')

    local_now = datetime.utcnow() + timedelta(hours=3)
    past_times = [
        (local_now - timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M'),
        (local_now - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
        (local_now - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
    ]
    schedule = CampaignSchedule(
        org_id=org.id,
        name='Multi-time',
        body='hello',
        sender_id=org.brand_name,
        scheduled_times=json.dumps(sorted(past_times)),
        status='active',
        next_run_at=datetime.utcnow() - timedelta(minutes=1),
    )
    db.session.add(schedule)
    db.session.commit()
    sid = schedule.id

    for _ in range(3):
        claim = sched_svc.claim_due_schedule()
        if claim is None:
            break
        schedule_id, fired = claim
        sched_svc.materialize_run(schedule_id, fired_iso=fired)

    campaigns = Campaign.query.filter_by(schedule_id=sid).all()
    assert len(campaigns) == 3, f'expected 3 campaigns, got {len(campaigns)}'
    schedule = db.session.get(CampaignSchedule, sid)
    assert schedule.status == 'completed'
    assert schedule.runs_completed == 3