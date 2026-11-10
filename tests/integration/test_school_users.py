"""Integration tests for school-admin user CRUD (A5).

Login helper mirrors tests/integration/test_permissions.py.
"""
from app.models import User


def _login(client, email, password='testpass123'):
    return client.post('/login',
                       data={'email': email, 'password': password},
                       follow_redirects=True)


def test_org_admin_can_list_users(client, app, db, associate_admin):
    _login(client, associate_admin.email, 'assocpass')
    resp = client.get('/school/users')
    assert resp.status_code == 200
    assert associate_admin.email.encode() in resp.data


def test_bursar_cannot_access_users(client, app, db, associate_admin):
    """Dept-scoped user gets 403."""
    bursar = User(email='b@test.local', full_name='B',
                  role='user', org_id=associate_admin.org_id,
                  department='bursar')
    bursar.set_password('bursarpass')
    db.session.add(bursar)
    db.session.commit()
    _login(client, 'b@test.local', 'bursarpass')
    resp = client.get('/school/users')
    assert resp.status_code == 403


def test_master_cannot_access_school_users(client, app, db, master_admin):
    _login(client, master_admin.email, 'masterpass')
    resp = client.get('/school/users')
    assert resp.status_code == 403


def test_create_user_with_department(client, app, db, associate_admin):
    _login(client, associate_admin.email, 'assocpass')
    resp = client.post('/school/users/new', data={
        'email': 'newbursar@test.local',
        'full_name': 'New Bursar',
        'password': 'testpass123',
        'role': 'user',
        'department': 'bursar',
    }, follow_redirects=True)
    assert resp.status_code == 200
    u = User.query.filter_by(email='newbursar@test.local').first()
    assert u is not None
    assert u.department == 'bursar'
    assert u.role == 'user'
    assert u.org_id == associate_admin.org_id


def test_create_user_invalid_department_rejected(client, app, db, associate_admin):
    _login(client, associate_admin.email, 'assocpass')
    resp = client.post('/school/users/new', data={
        'email': 'bad@test.local',
        'full_name': 'Bad',
        'password': 'testpass123',
        'role': 'user',
        'department': 'marketing',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert User.query.filter_by(email='bad@test.local').first() is None


def test_edit_user_changes_department(client, app, db, associate_admin):
    u = User(email='edit@test.local', full_name='Old',
             role='user', org_id=associate_admin.org_id,
             department=None)
    u.set_password('pass1234')
    db.session.add(u)
    db.session.commit()
    _login(client, associate_admin.email, 'assocpass')
    resp = client.post(f'/school/users/{u.id}/edit', data={
        'email': 'edit@test.local',
        'full_name': 'New',
        'department': 'dos',
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(u)
    assert u.department == 'dos'
    assert u.full_name == 'New'


def test_delete_last_admin_blocked(client, app, db, associate_admin):
    """associate_admin is the only admin -- delete should fail."""
    # Confirm only one admin in that org
    admins = User.query.filter_by(
        org_id=associate_admin.org_id, role='associate_admin').all()
    assert len(admins) == 1
    _login(client, associate_admin.email, 'assocpass')
    resp = client.post(f'/school/users/{associate_admin.id}/delete',
                       follow_redirects=True)
    assert resp.status_code == 200
    assert User.query.filter_by(id=associate_admin.id).first() is not None


def test_delete_user_succeeds(client, app, db, associate_admin):
    u = User(email='deletable@test.local', full_name='D',
             role='user', org_id=associate_admin.org_id)
    u.set_password('pass1234')
    db.session.add(u)
    db.session.commit()
    uid = u.id
    _login(client, associate_admin.email, 'assocpass')
    resp = client.post(f'/school/users/{uid}/delete', follow_redirects=True)
    assert resp.status_code == 200
    assert User.query.filter_by(id=uid).first() is None


def test_reset_password_changes_login(client, app, db, associate_admin):
    u = User(email='reset@test.local', full_name='R',
             role='user', org_id=associate_admin.org_id)
    u.set_password('oldpass123')
    db.session.add(u)
    db.session.commit()
    _login(client, associate_admin.email, 'assocpass')
    resp = client.post(f'/school/users/{u.id}/reset-password', data={
        'new_password': 'newpass456',
    }, follow_redirects=True)
    assert resp.status_code == 200
    # Log out, try new password
    client.get('/logout')
    resp2 = _login(client, 'reset@test.local', 'newpass456')
    assert resp2.status_code == 200
    assert b'Logout' in resp2.data or b'logout' in resp2.data.lower()


def test_org_isolation_via_edit(client, app, db, associate_admin, second_admin):
    """A user in org A cannot edit a user in org B via /school/users/<id>/edit."""
    other_user = User(email='otherorg@test.local', full_name='O',
                      role='user', org_id=second_admin.org_id)
    other_user.set_password('pass1234')
    db.session.add(other_user)
    db.session.commit()
    _login(client, associate_admin.email, 'assocpass')
    resp = client.get(f'/school/users/{other_user.id}/edit')
    assert resp.status_code == 404

def test_nav_users_link_visible_for_admin_only(
        client, app, db, associate_admin, master_admin):
    """base.html shows the Users nav link only for org-level school admins.

    Covers the {% if current_user.role == 'associate_admin'
    and not current_user.department %} guard in base.html.
    """
    # School admin sees the Users link (on a page they can reach)
    _login(client, associate_admin.email, 'assocpass')
    resp = client.get('/school/users')
    assert resp.status_code == 200
    assert b'/school/users' in resp.data

    # Master does not (on master's landing page)
    client.get('/logout')
    _login(client, master_admin.email, 'masterpass')
    resp2 = client.get('/master/')
    if resp2.status_code == 404:
        resp2 = client.get('/')
    assert resp2.status_code == 200
    assert b'/school/users' not in resp2.data


def test_nav_users_link_hidden_for_dept_user(
        client, app, db, associate_admin):
    """A department-scoped user (role=user, dept=bursar) also sees no Users link."""
    bursar = User(email='navb@test.local', full_name='NB',
                  role='user', org_id=associate_admin.org_id,
                  department='bursar')
    bursar.set_password('navpass123')
    db.session.add(bursar)
    db.session.commit()
    _login(client, 'navb@test.local', 'navpass123')
    resp = client.get('/profile/')
    assert resp.status_code == 200
    assert b'/school/users' not in resp.data
