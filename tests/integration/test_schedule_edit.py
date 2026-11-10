"""Integration tests for #16 schedules CRUD (edit + delete)."""
import json
from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models import Campaign, CampaignSchedule, WalletTransaction
from app.services import schedules as sched_svc
from app.services import wallet as wallet_svc
from tests.factories import ContactFactory, UserFactory


def _future_iso(days=7, hours=0):
    local = (datetime.utcnow() + timedelta(hours=3)
             + timedelta(days=days, hours=hours))
    return local.strftime('%Y-%m-%dT%H:%M')


def _make_contact(org, phone='256700000001', name='R'):
    return ContactFactory(org=org, phone=phone, name=name)


def _create_schedule(org, times, body='Hi {{name}}'):
    return sched_svc.create_schedule(
        org, name='Test sched', body=body, times=times,
        created_by=None, user=None)


# ---------------------------------------------------------------------------
# Edit -- basic
# ---------------------------------------------------------------------------

def test_edit_body_only_no_reservation_change(
        db, master_org, subscribed_associate):
    """Editing body only: refund full, re-debit same, net wallet unchanged."""
    org = subscribed_associate
    _make_contact(org)
    sched = _create_schedule(org, [_future_iso(1)])
    starting_balance = wallet_svc.get_balance(org.id)
    starting_reserved = sched.credits_reserved

    sched_svc.update_schedule(
        org, sched, name='Test sched', body='New body {{name}}',
        times=[_future_iso(1)])

    db.session.refresh(sched)
    assert sched.body == 'New body {{name}}'
    assert sched.credits_reserved == starting_reserved
    assert wallet_svc.get_balance(org.id) == starting_balance


def test_edit_add_time_increases_reservation(
        db, master_org, subscribed_associate):
    """Adding a time increases the reservation by one estimate."""
    org = subscribed_associate
    _make_contact(org)
    sched = _create_schedule(org, [_future_iso(1)])
    assert sched.credits_reserved == 1
    starting = wallet_svc.get_balance(org.id)

    sched_svc.update_schedule(
        org, sched, name='Test sched', body='Hi {{name}}',
        times=[_future_iso(1), _future_iso(2)])
    db.session.refresh(sched)
    assert sched.credits_reserved == 2
    assert wallet_svc.get_balance(org.id) == starting - 1


def test_edit_remove_time_decreases_reservation(
        db, master_org, subscribed_associate):
    """Removing a time decreases the reservation by one estimate."""
    org = subscribed_associate
    _make_contact(org)
    sched = _create_schedule(
        org, [_future_iso(1), _future_iso(2)])
    assert sched.credits_reserved == 2
    starting = wallet_svc.get_balance(org.id)

    sched_svc.update_schedule(
        org, sched, name='Test sched', body='Hi {{name}}',
        times=[_future_iso(1)])
    db.session.refresh(sched)
    assert sched.credits_reserved == 1
    assert wallet_svc.get_balance(org.id) == starting + 1


def test_edit_changes_group_and_recalculates(
        db, master_org, subscribed_associate):
    """Switching group changes the estimate based on new contact count."""
    from app.models import Group
    org = subscribed_associate
    _make_contact(org, phone='256700000001')
    _make_contact(org, phone='256700000002')

    g = Group(org_id=org.id, name='Two contacts')
    db.session.add(g)
    db.session.flush()

    # Reassign both contacts to group g
    from app.models import Contact
    Contact.query.filter_by(org_id=org.id).update({'group_id': g.id})
    db.session.commit()

    sched = _create_schedule(
        org, [_future_iso(1)])  # no group filter -> 2 contacts estimated
    assert sched.credits_reserved == 2

    # Switch to a different (empty) group -> estimate drops to 0
    # But create_schedule rejects zero recipients; update_schedule should too
    g2 = Group(org_id=org.id, name='Empty')
    db.session.add(g2)
    db.session.commit()

    with pytest.raises(sched_svc.ScheduleError,
                       match='No eligible recipients'):
        sched_svc.update_schedule(
            org, sched, name='Test sched', body='Hi {{name}}',
            times=[_future_iso(1)], group_id=g2.id)


def test_edit_rejects_cancelled_schedule(
        db, master_org, subscribed_associate):
    org = subscribed_associate
    _make_contact(org)
    sched = _create_schedule(org, [_future_iso(1)])
    sched_svc.cancel_schedule(sched)
    db.session.refresh(sched)

    with pytest.raises(sched_svc.ScheduleError,
                       match='Cannot edit a cancelled'):
        sched_svc.update_schedule(
            org, sched, name='New', body='Hi',
            times=[_future_iso(2)])


# ---------------------------------------------------------------------------
# Delete -- guards
# ---------------------------------------------------------------------------

def test_delete_rejects_active_schedule(
        db, master_org, subscribed_associate):
    org = subscribed_associate
    _make_contact(org)
    sched = _create_schedule(org, [_future_iso(1)])
    with pytest.raises(sched_svc.ScheduleError,
                       match='Cannot delete an active'):
        sched_svc.delete_schedule(org, sched)


def test_delete_rejects_fired_schedule(
        db, master_org, subscribed_associate):
    """Schedule with runs_completed > 0 cannot be deleted."""
    org = subscribed_associate
    _make_contact(org)
    sched = _create_schedule(org, [_future_iso(1)])
    # Manually mark fired (simulating past runs)
    sched.runs_completed = 2
    sched.status = 'cancelled'
    db.session.commit()

    with pytest.raises(sched_svc.ScheduleError,
                       match='already fired runs'):
        sched_svc.delete_schedule(org, sched)


def test_delete_cancelled_schedule_refunds_and_removes(
        db, master_org, subscribed_associate):
    """Cancelled schedule with remaining credits_reserved gets refunded + removed."""
    org = subscribed_associate
    _make_contact(org)
    sched = _create_schedule(org, [_future_iso(1)])
    assert sched.credits_reserved == 1
    # Set to cancelled but keep reservation (simulating direct status change)
    sched.status = 'cancelled'
    db.session.commit()
    sid = sched.id
    starting = wallet_svc.get_balance(org.id)

    sched_svc.delete_schedule(org, sched)
    assert CampaignSchedule.query.get(sid) is None
    assert wallet_svc.get_balance(org.id) == starting + 1