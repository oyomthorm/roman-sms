"""Tests for department-aware campaign filtering (A3d).

Request the `db` fixture from conftest so the app context is active.
"""
from app.models import Campaign
from app.services import campaigns as campaigns_svc
from tests.factories import OrgFactory, UserFactory


def _make_campaign(db, org, department, name, user_id=None):
    c = Campaign(
        org_id=org.id,
        name=name,
        body='Hello',
        sender_id='ROMANSMS',
        status='queued',
        total=0,
        department=department,
        created_by=user_id,
    )
    db.session.add(c)
    db.session.commit()
    return c


def test_bursar_sees_shared_and_own(db):
    org = OrgFactory()
    bursar = UserFactory(org=org, department='bursar')

    _make_campaign(db, org, None, 'shared', user_id=bursar.id)
    _make_campaign(db, org, 'bursar', 'bursar-only', user_id=bursar.id)
    _make_campaign(db, org, 'ht', 'ht-only', user_id=bursar.id)

    names = {c.name for c in campaigns_svc.list_for_org(org, user=bursar)}
    assert names == {'shared', 'bursar-only'}


def test_ht_user_sees_all(db):
    org = OrgFactory()
    ht = UserFactory(org=org, department=None)

    _make_campaign(db, org, None, 'shared', user_id=ht.id)
    _make_campaign(db, org, 'bursar', 'bursar-only', user_id=ht.id)
    _make_campaign(db, org, 'ht', 'ht-only', user_id=ht.id)

    names = {c.name for c in campaigns_svc.list_for_org(org, user=ht)}
    assert names == {'shared', 'bursar-only', 'ht-only'}


def test_get_for_user_blocks_foreign_department(db):
    org = OrgFactory()
    bursar = UserFactory(org=org, department='bursar')

    ht_only = _make_campaign(db, org, 'ht', 'ht-only', user_id=bursar.id)
    shared = _make_campaign(db, org, None, 'shared', user_id=bursar.id)

    assert campaigns_svc.get_for_user(org, ht_only.id, bursar) is None
    assert campaigns_svc.get_for_user(org, shared.id, bursar) is shared