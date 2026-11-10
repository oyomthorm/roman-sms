"""Tests for #44 -- schedule pre-reservation of credits.

Under #44, create_schedule pre-debits the wallet for the estimated total
across all runs, stores it in credits_reserved, and materialize_run
consumes from that reservation instead of re-debiting. Overages skip the
run; underages refund the difference at completion.

Two ways to set up schedules:

- ``_create_schedule`` -- goes through the public API. Times must be in
  the future (create_schedule validates this). Used by tests that only
  need a persisted schedule (creation, cancel).

- ``_make_reserved_schedule`` -- builds the row directly and debits the
  wallet manually, mimicking what create_schedule does. Bypasses
  _validate_times so past times work. Used by tests that need the schedule
  to actually fire (materialize behavior).

Uses subscribed_associate so check_can_send and wallet_svc.debit pass
(active subscription + funded wallet).
"""
import json
from datetime import datetime, timedelta

from app.extensions import db
from app.models import CampaignSchedule, Campaign, WalletTransaction
from app.services import schedules as sched_svc
from app.services import wallet as wallet_svc
from tests.factories import ContactFactory


def _future_iso(days=7, hours=0):
    """Local ISO datetime string N days in the future."""
    local = (datetime.utcnow() + timedelta(hours=3)
             + timedelta(days=days, hours=hours))
    return local.strftime('%Y-%m-%dT%H:%M')


def _past_iso(hours_ago=1):
    """Local ISO datetime string N hours in the past."""
    local = (datetime.utcnow() + timedelta(hours=3)
             - timedelta(hours=hours_ago))
    return local.strftime('%Y-%m-%dT%H:%M')


def _make_contact(org, phone='256700000001', name='Recipient'):
    return ContactFactory(org=org, phone=phone, name=name)


def _create_schedule(org, times, body='Hi {{name}}', name='Test sched'):
    """Create via the public API. Times must be future."""
    return sched_svc.create_schedule(
        org, name=name, body=body, times=times, created_by=None, user=None)


def _make_reserved_schedule(org, times, per_run_segments,
                            body='Hi {{name}}', name='Reserved sched'):
    """Build a due schedule directly with a manual debit.

    Bypasses _validate_times so past times are allowed. Debits the wallet
    by per_run_segments * len(times), mimicking create_schedule's #44
    reservation behavior.
    """
    total_reserved = per_run_segments * len(times)
    wallet_svc.debit(
        org.id, total_reserved,
        reason='schedule_reserve',
        note='Test fixture: manual reservation',
        actor_id=None,
    )
    schedule = CampaignSchedule(
        org_id=org.id,
        name=name,
        body=body,
        sender_id=org.brand_name,
        scheduled_times=json.dumps(sorted(times)),
        status='active',
        next_run_at=datetime.utcnow() - timedelta(minutes=1),
        credits_reserved=total_reserved,
    )
    db.session.add(schedule)
    db.session.commit()
    return schedule


# ---------------------------------------------------------------------------
# create_schedule (public API)
# ---------------------------------------------------------------------------

def test_create_schedule_debits_and_stores_reservation(
        db, master_org, subscribed_associate):
    org = subscribed_associate
    _make_contact(org)
    starting = wallet_svc.get_balance(org.id)

    sched = _create_schedule(org, [_future_iso()])

    assert sched.credits_reserved == 1
    assert wallet_svc.get_balance(org.id) == starting - 1
    tx = (WalletTransaction.query
          .filter_by(org_id=org.id, reason='schedule_reserve')
          .order_by(WalletTransaction.id.desc()).first())
    assert tx is not None and tx.delta == -1


def test_create_schedule_reserves_all_runs(
        db, master_org, subscribed_associate):
    org = subscribed_associate
    _make_contact(org)
    starting = wallet_svc.get_balance(org.id)

    sched = _create_schedule(
        org, [_future_iso(1), _future_iso(2), _future_iso(3)])

    assert sched.credits_reserved == 3
    assert wallet_svc.get_balance(org.id) == starting - 3


def test_create_schedule_rejects_zero_recipients(
        db, master_org, subscribed_associate):
    import pytest
    org = subscribed_associate
    with pytest.raises(sched_svc.ScheduleError,
                       match='No eligible recipients'):
        _create_schedule(org, [_future_iso()])


# ---------------------------------------------------------------------------
# cancel_schedule
# ---------------------------------------------------------------------------

def test_cancel_refunds_full_reservation(
        db, master_org, subscribed_associate):
    org = subscribed_associate
    _make_contact(org)
    sched = _create_schedule(org, [_future_iso(1), _future_iso(2)])
    assert sched.credits_reserved == 2
    balance_after_create = wallet_svc.get_balance(org.id)

    sched_svc.cancel_schedule(sched, actor_id=None)
    db.session.refresh(sched)

    assert sched.status == 'cancelled'
    assert sched.credits_reserved == 0
    assert wallet_svc.get_balance(org.id) == balance_after_create + 2
    tx = (WalletTransaction.query
          .filter_by(org_id=org.id, reason='schedule_cancel_refund')
          .order_by(WalletTransaction.id.desc()).first())
    assert tx is not None and tx.delta == 2


# ---------------------------------------------------------------------------
# materialize_run (#44 path) -- uses _make_reserved_schedule
# ---------------------------------------------------------------------------

def test_materialize_does_not_debit_again(
        db, master_org, subscribed_associate):
    org = subscribed_associate
    _make_contact(org)
    sched = _make_reserved_schedule(org, [_past_iso(1)], per_run_segments=1)
    sid = sched.id
    balance_after_create = wallet_svc.get_balance(org.id)
    assert sched.credits_reserved == 1

    claim = sched_svc.claim_due_schedule()
    assert claim is not None
    schedule_id, fired = claim
    sched_svc.materialize_run(schedule_id, fired_iso=fired)

    assert wallet_svc.get_balance(org.id) == balance_after_create
    db.session.refresh(sched)
    assert sched.credits_reserved == 0
    c = Campaign.query.filter_by(schedule_id=sid).first()
    assert c is not None
    assert c.credits_debited == 1


def test_materialize_overage_skips_and_pauses(
        db, master_org, subscribed_associate):
    org = subscribed_associate
    _make_contact(org, phone='256700000010', name='A')
    sched = _make_reserved_schedule(org, [_past_iso(1)], per_run_segments=1)
    sid = sched.id
    balance_after_create = wallet_svc.get_balance(org.id)

    # Add contacts so actual > reserved (3 > 1)
    _make_contact(org, phone='256700000011', name='B')
    _make_contact(org, phone='256700000012', name='C')

    claim = sched_svc.claim_due_schedule()
    schedule_id, fired = claim
    sched_svc.materialize_run(schedule_id, fired_iso=fired)

    assert Campaign.query.filter_by(schedule_id=sid).first() is None
    db.session.refresh(sched)
    assert sched.credits_reserved == 0
    assert wallet_svc.get_balance(org.id) == balance_after_create + 1
    assert sched.status == 'paused'
    assert 'Recipients grew' in (sched.pause_reason or '')


def test_materialize_exact_match_no_refund(
        db, master_org, subscribed_associate):
    org = subscribed_associate
    _make_contact(org)
    sched = _make_reserved_schedule(org, [_past_iso(1)], per_run_segments=1)
    sid = sched.id
    balance_after_create = wallet_svc.get_balance(org.id)

    claim = sched_svc.claim_due_schedule()
    schedule_id, fired = claim
    sched_svc.materialize_run(schedule_id, fired_iso=fired)

    db.session.refresh(sched)
    assert sched.status == 'completed'
    assert sched.credits_reserved == 0
    assert wallet_svc.get_balance(org.id) == balance_after_create
    refund = (WalletTransaction.query
              .filter_by(org_id=org.id, reason='schedule_complete_refund')
              .first())
    assert refund is None


def test_multi_run_reservation_decrements_across_fires(
        db, master_org, subscribed_associate):
    org = subscribed_associate
    _make_contact(org)
    sched = _make_reserved_schedule(
        org, [_past_iso(3), _past_iso(2), _past_iso(1)], per_run_segments=1)
    sid = sched.id
    assert sched.credits_reserved == 3

    for _ in range(3):
        claim = sched_svc.claim_due_schedule()
        if claim is None:
            break
        schedule_id, fired = claim
        sched_svc.materialize_run(schedule_id, fired_iso=fired)

    db.session.refresh(sched)
    assert sched.credits_reserved == 0
    assert sched.runs_completed == 3
    assert sched.status == 'completed'
    debit_count = (WalletTransaction.query
                   .filter_by(org_id=org.id, reason='schedule_reserve')
                   .count())
    assert debit_count == 1


# ---------------------------------------------------------------------------
# Legacy schedules (credits_reserved IS NULL)
# ---------------------------------------------------------------------------

def test_legacy_schedule_debits_at_fire(
        db, master_org, subscribed_associate):
    org = subscribed_associate
    _make_contact(org)
    schedule = CampaignSchedule(
        org_id=org.id, name='Legacy', body='Hi {{name}}',
        sender_id=org.brand_name,
        scheduled_times=json.dumps([_past_iso(1)]),
        status='active',
        next_run_at=datetime.utcnow() - timedelta(minutes=1),
        credits_reserved=None,
    )
    db.session.add(schedule)
    db.session.commit()
    sid = schedule.id
    balance_before = wallet_svc.get_balance(org.id)

    claim = sched_svc.claim_due_schedule()
    schedule_id, fired = claim
    sched_svc.materialize_run(schedule_id, fired_iso=fired)

    assert wallet_svc.get_balance(org.id) == balance_before - 1
    c = Campaign.query.filter_by(schedule_id=sid).first()
    assert c is not None


def test_cancel_legacy_schedule_no_refund(
        db, master_org, subscribed_associate):
    org = subscribed_associate
    _make_contact(org)
    schedule = CampaignSchedule(
        org_id=org.id, name='Legacy 2', body='Hi {{name}}',
        sender_id=org.brand_name,
        scheduled_times=json.dumps([_future_iso(1)]),
        status='active',
        next_run_at=datetime.utcnow() + timedelta(days=1),
        credits_reserved=None,
    )
    db.session.add(schedule)
    db.session.commit()
    balance_before = wallet_svc.get_balance(org.id)

    sched_svc.cancel_schedule(schedule, actor_id=None)
    db.session.refresh(schedule)

    assert schedule.status == 'cancelled'
    assert wallet_svc.get_balance(org.id) == balance_before