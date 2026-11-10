"""Integration tests for #45 Organization.vertical.

Covers:
  - create_associate accepts vertical='school'/'business'/'None'
  - update_associate sets/changes/clears vertical
  - invalid vertical values are rejected
  - existing orgs default to NULL
"""
import pytest

from app.extensions import db
from app.models import Organization
from app.services import orgs as orgs_svc
from tests.factories import OrgFactory, UserFactory


def _make_admin(org):
    return UserFactory(org=org, role='associate_admin')


# ---------------------------------------------------------------------------
# create_associate: vertical passed through
# ---------------------------------------------------------------------------

def test_create_associate_sets_vertical_school(db, master_org):
    org, admin = orgs_svc.create_associate(
        name='School One', slug='school-one', brand_name='S1',
        admin_email='s1@test.local', admin_password='pass1234',
        vertical='school',
    )
    assert org.vertical == 'school'


def test_create_associate_defaults_null_vertical(db, master_org):
    org, admin = orgs_svc.create_associate(
        name='No Vertical', slug='no-vert', brand_name='NV',
        admin_email='nv@test.local', admin_password='pass1234',
    )
    assert org.vertical is None


def test_create_associate_rejects_unknown_vertical(db, master_org):
    """Unknown value -> coerced to None (defensive normalization)."""
    org, admin = orgs_svc.create_associate(
        name='Weird', slug='weird', brand_name='W',
        admin_email='w@test.local', admin_password='pass1234',
        vertical='nonprofit',  # not in {'school','business'}
    )
    assert org.vertical is None  # coerced


# ---------------------------------------------------------------------------
# update_associate: change / clear vertical
# ---------------------------------------------------------------------------

def test_update_associate_sets_vertical(db):
    org = OrgFactory(vertical=None)
    orgs_svc.update_associate(org, vertical='business', actor_id=None)
    db.session.refresh(org)
    assert org.vertical == 'business'


def test_update_associate_clears_vertical_with_empty_string(db):
    org = OrgFactory(vertical='school')
    orgs_svc.update_associate(org, vertical='', actor_id=None)
    db.session.refresh(org)
    assert org.vertical is None


def test_update_associate_rejects_invalid_vertical(db):
    org = OrgFactory(vertical='school')
    with pytest.raises(orgs_svc.OrgError, match='Vertical must be'):
        orgs_svc.update_associate(org, vertical='nonprofit', actor_id=None)
    db.session.refresh(org)
    assert org.vertical == 'school'  # unchanged