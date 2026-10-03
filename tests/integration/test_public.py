from app.models import OptOut


def test_optout_landing_page(client):
    resp = client.get('/opt-out')
    assert resp.status_code == 200
    assert b'Opt out' in resp.data


def test_optout_via_form(client, app, db):
    resp = client.post('/opt-out', data={'phone': '0700123456'},
                       follow_redirects=True)
    assert resp.status_code == 200
    assert OptOut.query.filter_by(phone='256700123456').first() is not None


def test_optout_rejects_invalid_phone(client, app, db):
    resp = client.post('/opt-out', data={'phone': 'not-a-phone'})
    assert resp.status_code == 400
    assert OptOut.query.count() == 0


def test_optout_link_requires_confirmation(client, app, db):
    from app.services import optout_links
    app.config['PUBLIC_BASE_URL'] = 'https://example.test'
    token = optout_links.make_token('256700111222')

    # GET just shows the confirmation page
    resp = client.get(f'/opt-out/{token}')
    assert resp.status_code == 200
    assert OptOut.query.filter_by(phone='256700111222').first() is None

    # POST records it
    resp = client.post(f'/opt-out/{token}', follow_redirects=True)
    assert resp.status_code == 200
    assert OptOut.query.filter_by(phone='256700111222').first() is not None


def test_optout_token_invalid(client):
    resp = client.get('/opt-out/garbage-token')
    assert resp.status_code == 400


def test_forgot_password_does_not_leak_existence(client, app, db):
    # Email is not registered
    resp = client.post('/forgot-password',
                       data={'email': 'nobody@example.test'},
                       follow_redirects=True)
    assert resp.status_code == 200
    # Same message as for registered users
    assert b'If that email is registered' in resp.data


def test_forgot_password_for_registered_user(client, app, db,
                                             associate_admin):
    resp = client.post('/forgot-password',
                       data={'email': associate_admin.email},
                       follow_redirects=True)
    assert resp.status_code == 200
    # Console mailer — the token is logged but we cannot read it here.
    # Presence of a successful redirect is enough at this level.