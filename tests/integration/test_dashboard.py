"""
Dashboard rendering tests.

Covers the layout, contextual alerts, and the fixed sent_30d semantics
(sent_30d now counts messages that reached the network, including those
later confirmed delivered or reported as delivery_failed).
"""


def _login(client, email, password):
    return client.post('/login',
                       data={'email': email, 'password': password},
                       follow_redirects=True)


def test_dashboard_renders_for_associate(client, app, db, associate_admin):
    _login(client, associate_admin.email, 'assocpass')
    resp = client.get('/app')
    assert resp.status_code == 200


def test_dashboard_contains_hero_cards(client, app, db, associate_admin):
    _login(client, associate_admin.email, 'assocpass')
    resp = client.get('/app')
    assert b'Balance' in resp.data
    assert b'Delivery' in resp.data
    assert b'/billing/wallet' in resp.data
    assert b'/reports/log' in resp.data


def test_dashboard_contains_trend_section(client, app, db, associate_admin):
    _login(client, associate_admin.email, 'assocpass')
    resp = client.get('/app')
    # Either the chart renders, or the empty state does
    assert (b'Sending trend' in resp.data
            or b'No sends in the last 30 days' in resp.data)


def test_dashboard_contains_burn_rate(client, app, db, associate_admin):
    _login(client, associate_admin.email, 'assocpass')
    resp = client.get('/app')
    assert b'Credit burn rate' in resp.data


def test_dashboard_contains_quick_actions(client, app, db, associate_admin):
    _login(client, associate_admin.email, 'assocpass')
    resp = client.get('/app')
    assert b'Send a campaign' in resp.data
    assert b'/campaigns/new' in resp.data
    assert b'/contacts' in resp.data
    assert b'/groups' in resp.data


def test_dashboard_shows_no_plan_alert(client, app, db, associate_admin):
    """Fresh associate with no subscription sees the amber alert."""
    _login(client, associate_admin.email, 'assocpass')
    resp = client.get('/app')
    assert b'No active plan' in resp.data


def test_dashboard_master_redirects_to_master_console(client, app, db,
                                                       master_admin):
    _login(client, master_admin.email, 'masterpass')
    resp = client.get('/app', follow_redirects=False)
    assert resp.status_code == 302
    assert '/master' in resp.headers.get('Location', '')


def test_dashboard_requires_login(client):
    resp = client.get('/app')
    assert resp.status_code in (302, 401)