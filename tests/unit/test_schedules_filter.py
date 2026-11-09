"""Tests for department-aware schedule filtering (A3a).

All tests request the `db` fixture from tests/conftest.py so the app
context is active (conftest's `app` fixture yields inside
`with app.app_context()`).
"""
import json
from datetime import datetime, timedelta

from app.models import CampaignSchedule
from app.services import schedules as schedules_svc
from tests.factories import OrgFactory, UserFactory


def _make_schedule(db, org, department, name='s',
                   status='active', created_by=None):
    """Build a minimal CampaignSchedule with the four required columns."""
    s = CampaignSchedule(
        org_id=org.id,
        name=name,
        body='Hello',
        sender_id='ROMANSMS',
        scheduled_times=json.dumps(['2099-01-01T09:00']),
        department=department,
        status=status,
        next_run_at=datetime.utcnow() + timedelta(hours=1),
        created_by=created_by,
    )
    db.session.add(s)
    db.session.commit()
    return s


def test_bursar_sees_shared_and_own(db):
    org = OrgFactory()
    bursar = UserFactory(org=org, department='bursar')

    _make_schedule(db, org, None, 'shared')
    _make_schedule(db, org, 'bursar', 'bursar-only')
    _make_schedule(db, org, 'ht', 'ht-only')

    names = {s.name for s in schedules_svc.list_for_org(org, user=bursar)}
    assert names == {'shared', 'bursar-only'}


def test_ht_user_sees_all(db):
    org = OrgFactory()
    ht = UserFactory(org=org, department=None)

    _make_schedule(db, org, None, 'shared')
    _make_schedule(db, org, 'bursar', 'bursar-only')
    _make_schedule(db, org, 'ht', 'ht-only')

    names = {s.name for s in schedules_svc.list_for_org(org, user=ht)}
    assert names == {'shared', 'bursar-only', 'ht-only'}


def test_get_for_user_blocks_foreign_department(db):
    org = OrgFactory()
    bursar = UserFactory(org=org, department='bursar')

    ht_only = _make_schedule(db, org, 'ht', 'ht-only')
    shared  = _make_schedule(db, org, None, 'shared')

    assert schedules_svc.get_for_user(org, ht_only.id, bursar) is None
    assert schedules_svc.get_for_user(org, shared.id,  bursar) is shared