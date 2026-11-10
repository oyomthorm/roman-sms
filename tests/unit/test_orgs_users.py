"""Tests for school user CRUD in services.orgs (A5a).

Request the `db` fixture from conftest so app context is active.
"""
import pytest

from app.models import User
from app.services import orgs as orgs_svc
from tests.factories import OrgFactory, UserFactory


def test_create_user_with_each_department(db):
    org = OrgFactory()
    admin = UserFactory(org=org, role='associate_admin', department=None)

    for dept in [None, 'bursar', 'dos', 'dean', 'ht']:
        u = orgs_svc.create_user(
            org,
            email=f'u-{dept or "shared"}@test.local',
            full_name=f'User {dept or "shared"}',
            password='pass1234',
            role='user' if dept else 'associate_admin',
            department=dept,
            actor_id=admin.id,
        )
        assert u.department == dept
        assert u.org_id == org.id


def test_create_user_rejects_master_role(db):
    org = OrgFactory()
    admin = UserFactory(org=org, role='associate_admin')
    with pytest.raises(orgs_svc.OrgError, match='Invalid role'):
        orgs_svc.create_user(
            org, email='x@test.local', full_name='X',
            password='pass1234', role='master_admin',
            actor_id=admin.id)


def test_create_user_rejects_bad_department(db):
    org = OrgFactory()
    admin = UserFactory(org=org, role='associate_admin')
    with pytest.raises(orgs_svc.OrgError, match='Invalid department'):
        orgs_svc.create_user(
            org, email='x@test.local', full_name='X',
            password='pass1234', role='user', department='marketing',
            actor_id=admin.id)


def test_create_user_rejects_dept_scoped_admin(db):
    org = OrgFactory()
    admin = UserFactory(org=org, role='associate_admin')
    with pytest.raises(orgs_svc.OrgError, match='cannot be scoped'):
        orgs_svc.create_user(
            org, email='x@test.local', full_name='X',
            password='pass1234', role='associate_admin', department='bursar',
            actor_id=admin.id)


def test_create_user_rejects_duplicate_email(db):
    org = OrgFactory()
    admin = UserFactory(org=org, role='associate_admin')
    orgs_svc.create_user(
        org, email='dup@test.local', full_name='A',
        password='pass1234', role='associate_admin', actor_id=admin.id)
    with pytest.raises(orgs_svc.OrgError, match='already registered'):
        orgs_svc.create_user(
            org, email='dup@test.local', full_name='B',
            password='pass1234', role='associate_admin', actor_id=admin.id)


def test_update_user_changes_department_and_name(db):
    org = OrgFactory()
    admin = UserFactory(org=org, role='associate_admin')
    u = orgs_svc.create_user(
        org, email='u@test.local', full_name='Before',
        password='pass1234', role='user', department=None, actor_id=admin.id)

    orgs_svc.update_user(org, u.id, full_name='After',
                         department='bursar', actor_id=admin.id)
    db.session.refresh(u)
    assert u.full_name == 'After'
    assert u.department == 'bursar'


def test_delete_user_refuses_last_admin(db):
    org = OrgFactory()
    # Only one associate_admin in this org (the UserFactory default)
    admin = UserFactory(org=org, role='associate_admin')
    with pytest.raises(orgs_svc.OrgError, match='last school admin'):
        orgs_svc.delete_user(org, admin.id, actor_id=admin.id)


def test_delete_user_succeeds_when_another_admin_exists(db):
    org = OrgFactory()
    admin1 = UserFactory(org=org, role='associate_admin', email='a1@test.local')
    admin2 = UserFactory(org=org, role='associate_admin', email='a2@test.local')
    orgs_svc.delete_user(org, admin1.id, actor_id=admin2.id)
    assert User.query.filter_by(id=admin1.id).first() is None