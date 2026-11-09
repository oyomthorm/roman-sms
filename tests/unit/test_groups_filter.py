"""Tests for department-aware group filtering (A3b).

Request the `db` fixture from conftest so the app context is active.
"""
from app.models import Group
from app.services import groups as groups_svc
from tests.factories import OrgFactory, UserFactory


def _make_group(db, org, department, name):
    g = Group(org_id=org.id, name=name, department=department)
    db.session.add(g)
    db.session.commit()
    return g


def test_bursar_sees_shared_and_own(db):
    org = OrgFactory()
    bursar = UserFactory(org=org, department='bursar')

    _make_group(db, org, None, 'shared')
    _make_group(db, org, 'bursar', 'bursar-only')
    _make_group(db, org, 'ht', 'ht-only')

    names = {g.name for g, _ in groups_svc.list_groups(org, user=bursar)}
    assert names == {'shared', 'bursar-only'}


def test_ht_user_sees_all(db):
    org = OrgFactory()
    ht = UserFactory(org=org, department=None)

    _make_group(db, org, None, 'shared')
    _make_group(db, org, 'bursar', 'bursar-only')
    _make_group(db, org, 'ht', 'ht-only')

    names = {g.name for g, _ in groups_svc.list_groups(org, user=ht)}
    assert names == {'shared', 'bursar-only', 'ht-only'}


def test_get_for_user_blocks_foreign_department(db):
    org = OrgFactory()
    bursar = UserFactory(org=org, department='bursar')

    ht_only = _make_group(db, org, 'ht', 'ht-only')
    shared = _make_group(db, org, None, 'shared')

    assert groups_svc.get_for_user(org, ht_only.id, bursar) is None
    assert groups_svc.get_for_user(org, shared.id, bursar) is shared


def test_create_inherits_department(db):
    org = OrgFactory()
    bursar = UserFactory(org=org, department='bursar')

    g = groups_svc.create(org, name='new-bursar-group',
                          description=None,
                          department=bursar.department,
                          actor_id=bursar.id)

    assert g.department == 'bursar'
    # Should not be visible to a user in a different department
    ht = UserFactory(org=org, department='ht')
    visible = {x.name for x, _ in groups_svc.list_groups(org, user=ht)}
    assert 'new-bursar-group' not in visible