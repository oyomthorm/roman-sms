"""Integration tests for #46 user lifecycle (suspend/terminate/reactivate).

Covers:
  - Suspended user cannot initiate sends, but CAN log in
  - Terminated user cannot log in (is_active_flag=False)
  - Reactivate restores login and send permission
  - Guards: cannot suspend/terminate self, cannot suspend/terminate last admin
  - status_changed_at is set on each transition
"""
from app.extensions import db
from app.models import User
from app.services import orgs as orgs_svc
from tests.factories import UserFactory


def _login(client, email, password):
    return client.post('/login',
                       data={'email': email, 'password': password},
                       follow_redirects=True)


def _logout(client):
    return client.get('/logout', follow_redirects=True)


# ---------------------------------------------------------------------------
# Terminate blocks login
# ---------------------------------------------------------------------------

def test_terminated_user_cannot_login(
        client, app, db, associate_admin):
    """Terminated user's is_active_flag=False -> login rejected."""
    victim = UserFactory(org=associate_admin.organization,
                         email='terminate@test.local',
                         password='testpass123',
                         role='associate_admin')
    orgs_svc.terminate_user(associate_admin.organization, victim.id,
                            actor_id=associate_admin.id)
    db.session.refresh(victim)
    assert victim.status == 'terminated'
    assert victim.is_active_flag is False

    resp = _login(client, 'terminate@test.local', 'testpass123')
    assert resp.status_code == 200
    assert b'Invalid email or password' in resp.data


# ---------------------------------------------------------------------------
# Suspend does NOT block login
# ---------------------------------------------------------------------------

def test_suspended_user_can_still_login(
        client, app, db, associate_admin):
    victim = UserFactory(org=associate_admin.organization,
                         email='susp@test.local',
                         password='testpass123',
                         role='associate_admin')
    orgs_svc.suspend_user(associate_admin.organization, victim.id,
                          actor_id=associate_admin.id)
    db.session.refresh(victim)
    assert victim.status == 'suspended'
    assert victim.is_active_flag is True  # login still allowed

    resp = _login(client, 'susp@test.local', 'testpass123')
    assert resp.status_code == 200
    # Failed login would contain the error flash
    assert b'Invalid email or password' not in resp.data


# ---------------------------------------------------------------------------
# Suspended user cannot create a send
# ---------------------------------------------------------------------------

def test_suspended_user_cannot_create_campaign(
        client, app, db, associate_admin, subscribed_associate):
    """POST /campaigns/new by a suspended user -> flash + no campaign."""
    from app.models import Campaign

    org = subscribed_associate
    victim = UserFactory(org=org, email='susp-send@test.local',
                         password='testpass123',
                         role='associate_admin', department=None)
    orgs_svc.suspend_user(org, victim.id, actor_id=associate_admin.id)

    _login(client, 'susp-send@test.local', 'testpass123')
    resp = client.post('/campaigns/new', data={
        'name': 'Suspended attempt',
        'body': 'Hello',
        'mode': 'now',
        'recipient_source': 'paste',
        'pasted_numbers': '256700000001',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'suspended' in resp.data.lower()
    # No campaign created
    c = Campaign.query.filter_by(name='Suspended attempt').first()
    assert c is None


# ---------------------------------------------------------------------------
# Reactivate restores everything
# ---------------------------------------------------------------------------

def test_reactivate_restores_login(
        client, app, db, associate_admin):
    victim = UserFactory(org=associate_admin.organization,
                         email='react@test.local',
                         password='testpass123',
                         role='associate_admin')
    orgs_svc.terminate_user(associate_admin.organization, victim.id,
                            actor_id=associate_admin.id)
    # Confirm blocked
    resp = _login(client, 'react@test.local', 'testpass123')
    assert b'Invalid email or password' in resp.data

    # Reactivate
    orgs_svc.reactivate_user(associate_admin.organization, victim.id,
                             actor_id=associate_admin.id)
    db.session.refresh(victim)
    assert victim.status == 'active'
    assert victim.is_active_flag is True

    # Now login works
    _logout(client)
    resp2 = _login(client, 'react@test.local', 'testpass123')
    assert resp2.status_code == 200
    assert b'Invalid email or password' not in resp2.data


# ---------------------------------------------------------------------------
# Guard: cannot suspend self
# ---------------------------------------------------------------------------

def test_cannot_suspend_self(client, app, db, associate_admin):
    import pytest
    with pytest.raises(orgs_svc.OrgError, match='cannot suspend yourself'):
        orgs_svc.suspend_user(associate_admin.organization,
                              associate_admin.id,
                              actor_id=associate_admin.id)


def test_cannot_terminate_self(client, app, db, associate_admin):
    import pytest
    with pytest.raises(orgs_svc.OrgError, match='cannot terminate yourself'):
        orgs_svc.terminate_user(associate_admin.organization,
                                associate_admin.id,
                                actor_id=associate_admin.id)


# ---------------------------------------------------------------------------
# Guard: cannot suspend/terminate last active admin
# ---------------------------------------------------------------------------

def test_cannot_suspend_last_admin(client, app, db, associate_admin):
    """Only one active associate_admin in this org -> refuse."""
    import pytest
    # Ensure only one admin (associate_admin is the fixture)
    admins = User.query.filter_by(
        org_id=associate_admin.org_id,
        role='associate_admin',
        status='active').all()
    assert len(admins) == 1

    # Acting admin is a different user (a second non-admin) to avoid self-check
    actor = UserFactory(org=associate_admin.organization,
                        email='actor@test.local',
                        role='user', department='bursar')
    with pytest.raises(orgs_svc.OrgError, match='last active school admin'):
        orgs_svc.suspend_user(associate_admin.organization,
                              associate_admin.id,
                              actor_id=actor.id)


# ---------------------------------------------------------------------------
# status_changed_at is set
# ---------------------------------------------------------------------------

def test_status_changed_at_set_on_transition(client, app, db, associate_admin):
    victim = UserFactory(org=associate_admin.organization,
                         email='transition@test.local',
                         role='associate_admin')
    assert victim.status_changed_at is None

    orgs_svc.suspend_user(associate_admin.organization, victim.id,
                          actor_id=associate_admin.id)
    db.session.refresh(victim)
    assert victim.status == 'suspended'
    assert victim.status_changed_at is not None
    first_change = victim.status_changed_at

    # Suspend again -> error, status_changed_at unchanged
    import pytest
    with pytest.raises(orgs_svc.OrgError, match='already suspended'):
        orgs_svc.suspend_user(associate_admin.organization, victim.id,
                              actor_id=associate_admin.id)
    db.session.refresh(victim)
    assert victim.status_changed_at == first_change