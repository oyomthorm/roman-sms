"""Integration tests for #47 user detail page."""
from app.extensions import db
from app.models import Campaign, CampaignSchedule, AuditLog, User
from app.services import orgs as orgs_svc
from tests.factories import UserFactory


def _login(client, email, password):
    return client.post('/login',
                       data={'email': email, 'password': password},
                       follow_redirects=True)


def test_user_detail_renders_for_admin(client, app, db, associate_admin):
    _login(client, associate_admin.email, 'assocpass')
    resp = client.get(f'/school/users/{associate_admin.id}')
    assert resp.status_code == 200
    assert associate_admin.email.encode() in resp.data
    assert b'Recent campaigns' in resp.data
    assert b'Recent schedules' in resp.data
    assert b'Recent activity' in resp.data


def test_user_detail_404_for_foreign_user(
        client, app, db, associate_admin, second_admin):
    """A user from a different org -> 404."""
    other_user = UserFactory(org=second_admin.organization,
                              email='foreign@test.local',
                              role='user', department='bursar')
    _login(client, associate_admin.email, 'assocpass')
    resp = client.get(f'/school/users/{other_user.id}')
    assert resp.status_code == 404


def test_user_detail_shows_recent_activity(
        client, app, db, associate_admin):
    """If the user has audit entries, they show in the activity table."""
    # Create an audit log entry for the admin
    log = AuditLog(
        actor_id=associate_admin.id,
        org_id=associate_admin.org_id,
        action='test_action',
        detail='Test detail for #47',
    )
    db.session.add(log)
    db.session.commit()

    _login(client, associate_admin.email, 'assocpass')
    resp = client.get(f'/school/users/{associate_admin.id}')
    assert resp.status_code == 200
    assert b'test_action' in resp.data
    assert b'Test detail for #47' in resp.data


def test_user_detail_shows_campaigns(
        client, app, db, associate_admin):
    """If the user has campaigns, they show in the campaigns table."""
    from tests.factories import make_campaign  # helper-style factory
    camp = make_campaign(
        associate_admin.organization, associate_admin,
        name='Detail test campaign', body='Hello', total=5)
    _login(client, associate_admin.email, 'assocpass')
    resp = client.get(f'/school/users/{associate_admin.id}')
    assert resp.status_code == 200
    assert b'Detail test campaign' in resp.data