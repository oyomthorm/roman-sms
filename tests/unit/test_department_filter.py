"""Tests for department_filter and the department-aware service layer."""
import pytest

from app.extensions import db
from app.models import Group, MessageTemplate, Campaign, CampaignSchedule
from app.permissions import department_filter
from app.services import groups as groups_svc
from app.services import templates_svc
from app.services import campaigns as campaigns_svc
from app.services import schedules as schedules_svc
from tests.factories import ContactFactory, OrgFactory, UserFactory


# ---------------------------------------------------------------------------
# Helper: fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def org(db):
    return OrgFactory()


@pytest.fixture
def bursar(db, org):
    return UserFactory(org=org, role='associate_admin', department='bursar')


@pytest.fixture
def dos(db, org):
    return UserFactory(org=org, role='associate_admin', department='dos')


@pytest.fixture
def ht(db, org):
    """Head teacher - department=None sees everything."""
    return UserFactory(org=org, role='associate_admin', department=None)


# ---------------------------------------------------------------------------
# The filter helper itself
# ---------------------------------------------------------------------------

@pytest.fixture
def subscribed_bursar(db, subscribed_associate):
    """Bursar attached to a subscribed (plan-active) org."""
    return UserFactory(org=subscribed_associate, role='associate_admin',
                       department='bursar')

def test_filter_none_user_returns_all(app, db, org, bursar):
    groups_svc.create(org, name='Bursar A', department='bursar')
    groups_svc.create(org, name='DOS A', department='dos')
    groups_svc.create(org, name='Shared', department=None)

    # user=None -> no filter
    result = groups_svc.list_groups(org, user=None)
    names = {g.name for g, _ in result}
    assert names == {'Bursar A', 'DOS A', 'Shared'}


def test_filter_none_department_user_sees_all(app, db, org, ht):
    groups_svc.create(org, name='Bursar A', department='bursar')
    groups_svc.create(org, name='DOS A', department='dos')
    groups_svc.create(org, name='Shared', department=None)

    result = groups_svc.list_groups(org, user=ht)
    names = {g.name for g, _ in result}
    assert names == {'Bursar A', 'DOS A', 'Shared'}


def test_filter_bursar_sees_bursar_and_shared(app, db, org, bursar):
    groups_svc.create(org, name='Bursar A', department='bursar')
    groups_svc.create(org, name='DOS A', department='dos')
    groups_svc.create(org, name='Shared', department=None)

    result = groups_svc.list_groups(org, user=bursar)
    names = {g.name for g, _ in result}
    assert names == {'Bursar A', 'Shared'}
    assert 'DOS A' not in names


def test_filter_bursar_does_not_see_dos(app, db, org, bursar):
    groups_svc.create(org, name='DOS Secret', department='dos')
    result = groups_svc.list_groups(org, user=bursar)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# Group create / list with department
# ---------------------------------------------------------------------------

def test_create_group_with_department(app, db, org):
    g = groups_svc.create(org, name='Bursar Group', department='bursar')
    assert g.department == 'bursar'
    # Fetch from DB to prove it persisted
    db.session.expire_all()
    g2 = Group.query.get(g.id)
    assert g2.department == 'bursar'


def test_create_group_without_department(app, db, org):
    g = groups_svc.create(org, name='Shared Group')
    assert g.department is None


# ---------------------------------------------------------------------------
# Template create / list with department
# ---------------------------------------------------------------------------

def test_create_template_with_department(app, db, org):
    t = templates_svc.create_template(org, name='Fee reminder',
                                       body='Hi {{name}}',
                                       department='bursar')
    assert t.department == 'bursar'


def test_list_templates_filters_by_user(app, db, org, bursar):
    templates_svc.create_template(org, name='Bursar T',
                                   body='x', department='bursar')
    templates_svc.create_template(org, name='DOS T',
                                   body='y', department='dos')
    templates_svc.create_template(org, name='Shared T',
                                   body='z', department=None)

    result = templates_svc.list_templates(org, user=bursar)
    names = {t.name for t in result}
    assert names == {'Bursar T', 'Shared T'}


# ---------------------------------------------------------------------------
# Campaign create / list with department
# ---------------------------------------------------------------------------

def test_create_campaign_sets_department_from_user(app, db,
                                                    subscribed_associate,
                                                    subscribed_bursar):
    """Campaign created by a bursar carries department='bursar'."""
    ContactFactory(org_id=subscribed_associate.id)

    campaign, _ = campaigns_svc.create_campaign(
        subscribed_associate, name='Fee reminder', body='Hi {{name}}',
        created_by=subscribed_bursar.id, user=subscribed_bursar,
    )
    assert campaign.department == 'bursar'


def test_create_campaign_without_user(app, db, subscribed_associate):
    ContactFactory(org_id=subscribed_associate.id)

    campaign, _ = campaigns_svc.create_campaign(
        subscribed_associate, name='Shared', body='Hi {{name}}', user=None,
    )
    assert campaign.department is None


# ---------------------------------------------------------------------------
# Schedule create with department
# ---------------------------------------------------------------------------

def test_create_schedule_sets_department_from_user(app, db, org, bursar):
    from datetime import datetime, timedelta
    future = (datetime.utcnow() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M')
    sched = schedules_svc.create_schedule(
        org,
        name='Weekly fee reminder',
        body='Hi {{name}}',
        times=[future],
        created_by=bursar.id,
        user=bursar,
    )
    assert sched.department == 'bursar'