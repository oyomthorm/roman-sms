"""Tests for department-aware template filtering (A3c).

Request the `db` fixture from conftest so the app context is active.
"""
from app.models import MessageTemplate
from app.services import templates_svc
from tests.factories import OrgFactory, UserFactory


def _make_template(db, org, department, name):
    t = MessageTemplate(org_id=org.id, name=name, body='Hello',
                        department=department)
    db.session.add(t)
    db.session.commit()
    return t


def test_bursar_sees_shared_and_own(db):
    org = OrgFactory()
    bursar = UserFactory(org=org, department='bursar')

    _make_template(db, org, None, 'shared')
    _make_template(db, org, 'bursar', 'bursar-only')
    _make_template(db, org, 'ht', 'ht-only')

    names = {t.name for t in templates_svc.list_templates(org, user=bursar)}
    assert names == {'shared', 'bursar-only'}


def test_ht_user_sees_all(db):
    org = OrgFactory()
    ht = UserFactory(org=org, department=None)

    _make_template(db, org, None, 'shared')
    _make_template(db, org, 'bursar', 'bursar-only')
    _make_template(db, org, 'ht', 'ht-only')

    names = {t.name for t in templates_svc.list_templates(org, user=ht)}
    assert names == {'shared', 'bursar-only', 'ht-only'}


def test_get_for_user_blocks_foreign_department(db):
    org = OrgFactory()
    bursar = UserFactory(org=org, department='bursar')

    ht_only = _make_template(db, org, 'ht', 'ht-only')
    shared = _make_template(db, org, None, 'shared')

    assert templates_svc.get_for_user(org, ht_only.id, bursar) is None
    assert templates_svc.get_for_user(org, shared.id, bursar) is shared