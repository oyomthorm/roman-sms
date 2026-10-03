from datetime import datetime, timedelta
from tests.factories import OrgFactory, UserFactory, PlanFactory


def _login_master(client, master_admin):
    client.post('/login', data={
        'email': master_admin.email,
        'password': 'masterpass',
    }, follow_redirects=True)


def test_master_can_create_org(client, app, db, master_admin):
    _login_master(client, master_admin)

    resp = client.post('/master/orgs/new', data={
        'name': 'Kampalafit',
        'slug': 'kampalafit',
        'brand_name': 'Kampalafit',
        'admin_email': 'owner@kfit.test',
        'admin_password': 'pass12345',
    }, follow_redirects=True)
    assert resp.status_code == 200

    from app.models import Organization, User
    org = Organization.query.filter_by(slug='kampalafit').first()
    assert org is not None
    admin = User.query.filter_by(email='owner@kfit.test').first()
    assert admin.org_id == org.id


def test_master_can_grant_credits(client, app, db, master_admin, associate_org):
    _login_master(client, master_admin)
    from app.services.wallet import get_balance
    assert get_balance(associate_org.id) == 0

    client.post(f'/master/orgs/{associate_org.id}/grant',
                data={'amount': '250', 'note': 'test'},
                follow_redirects=True)

    assert get_balance(associate_org.id) == 250


def test_master_can_assign_plan(client, app, db, master_admin,
                                associate_org, plan):
    _login_master(client, master_admin)

    client.post(f'/master/orgs/{associate_org.id}/plan',
                data={'plan_id': str(plan.id), 'credit_wallet': '1'},
                follow_redirects=True)

    from app.services.wallet import get_balance
    from app.services.subscriptions import current_for
    assert get_balance(associate_org.id) == plan.credits
    sub = current_for(associate_org.id)
    assert sub is not None
    assert sub.plan_id == plan.id


def test_master_can_suspend_and_reactivate(client, app, db,
                                           master_admin, associate_org):
    _login_master(client, master_admin)

    client.post(f'/master/orgs/{associate_org.id}/suspend',
                data={'reason': 'test'}, follow_redirects=True)
    db.session.refresh(associate_org)
    assert associate_org.status == 'suspended'

    client.post(f'/master/orgs/{associate_org.id}/activate',
                follow_redirects=True)
    db.session.refresh(associate_org)
    assert associate_org.status == 'active'


def test_associate_cannot_reach_master_routes(client, app, db,
                                              associate_admin):
    client.post('/login', data={
        'email': associate_admin.email,
        'password': 'assocpass',
    }, follow_redirects=True)
    for path in ['/master/', '/master/orgs', '/master/plans', '/master/audit']:
        resp = client.get(path)
        assert resp.status_code == 403, path