from app.services import wallet as wallet_svc
from tests.factories import ContactFactory


def test_full_campaign_flow(client, app, db, associate_admin,
                            subscribed_associate):
    org = subscribed_associate
    for _ in range(2):
        ContactFactory(org_id=org.id)

    # Log in as associate
    client.post('/login', data={
        'email': associate_admin.email,
        'password': 'assocpass',
    }, follow_redirects=True)

    starting = wallet_svc.get_balance(org.id)
    resp = client.post('/campaigns/new', data={
        'name': 'Smoke test',
        'body': 'Hi {{name}}',
    }, follow_redirects=True)
    assert resp.status_code == 200

    from app.models import Campaign, SendQueue
    c = Campaign.query.filter_by(org_id=org.id).first()
    assert c is not None
    assert c.status == 'queued'
    assert c.total == 2
    assert wallet_svc.get_balance(org.id) == starting - 2
    assert SendQueue.query.filter_by(campaign_id=c.id).count() == 1


def test_campaign_route_rejects_empty_body(client, app, db, associate_admin,
                                            subscribed_associate):
    client.post('/login', data={
        'email': associate_admin.email,
        'password': 'assocpass',
    }, follow_redirects=True)

    resp = client.post('/campaigns/new', data={
        'name': 'Bad', 'body': '',
    }, follow_redirects=True)
    assert b'required' in resp.data.lower()

    from app.models import Campaign
    assert Campaign.query.filter_by(org_id=subscribed_associate.id).count() == 0


def test_reports_route_requires_login(client):
    resp = client.get('/reports/log')
    assert resp.status_code in (302, 401)


# ---------------------------------------------------------------------------
# Paste-numbers recipient source (shipped in 0.8.1; route wiring was the
# missing piece — the service layer handled custom_phones but the route
# never read the form field or passed it through).
# ---------------------------------------------------------------------------


def test_campaign_paste_numbers_via_route(client, app, db,
                                          associate_admin,
                                          subscribed_associate):
    """
    POST to /campaigns/new with recipient_source=paste and a mixed blob
    of phone numbers. Expect: duplicates dropped, landline dropped,
    campaign created, MessageLog rows only for the eligible mobiles.
    """
    from app.models import Campaign, MessageLog

    org = subscribed_associate

    client.post('/login', data={
        'email': associate_admin.email,
        'password': 'assocpass',
    }, follow_redirects=True)

    pasted = '\n'.join([
        '0700123456',   # ok
        '0700123456',   # duplicate of above
        '0752123456',   # ok
        '0772123456',   # ok
        '0782123456',   # ok
        '0703123456',   # ok
        '0704123456',   # ok
        '0705123456',   # ok
        '0706123456',   # ok
        '0414123456',   # landline — should be dropped
        'not a phone',  # garbage — should be dropped
    ])

    resp = client.post('/campaigns/new', data={
        'mode': 'now',
        'recipient_source': 'paste',
        'name': 'Paste route test',
        'body': 'Hello from a pasted list',
        'pasted_numbers': pasted,
    }, follow_redirects=False)

    assert resp.status_code == 302
    assert '/campaigns/' in resp.headers['Location']

    campaign = (Campaign.query
                .filter_by(org_id=org.id)
                .order_by(Campaign.id.desc())
                .first())
    assert campaign is not None
    assert campaign.name == 'Paste route test'
    # 8 unique mobiles: 9 valid lines minus the duplicate = 8
    assert campaign.total == 8

    logs = MessageLog.query.filter_by(campaign_id=campaign.id).all()
    assert len(logs) == 8

    phones = {log.phone for log in logs}
    assert phones == {
        '256700123456', '256752123456', '256772123456',
        '256782123456', '256703123456', '256704123456',
        '256705123456', '256706123456',
    }
    # The landline and the garbage never made it in.
    assert '256414123456' not in phones


def test_campaign_paste_numbers_rejects_empty_list(
        client, app, db, associate_admin, subscribed_associate):
    """Empty or all-garbage paste → flash + re-render, no Campaign row."""
    from app.models import Campaign

    org = subscribed_associate

    client.post('/login', data={
        'email': associate_admin.email,
        'password': 'assocpass',
    }, follow_redirects=True)

    before = Campaign.query.filter_by(org_id=org.id).count()

    resp = client.post('/campaigns/new', data={
        'mode': 'now',
        'recipient_source': 'paste',
        'name': 'Should fail',
        'body': 'nope',
        'pasted_numbers': 'garbage\nmore garbage\n0414123456',
    }, follow_redirects=True)

    # Stays on the form with a flash, no new campaign.
    assert resp.status_code == 200
    assert b'No valid phone numbers' in resp.data

    after = Campaign.query.filter_by(org_id=org.id).count()
    assert after == before


def test_campaign_paste_numbers_not_allowed_with_schedule(
        client, app, db, associate_admin, subscribed_associate):
    """mode=schedule + recipient_source=paste is refused."""
    from app.models import CampaignSchedule

    org = subscribed_associate

    client.post('/login', data={
        'email': associate_admin.email,
        'password': 'assocpass',
    }, follow_redirects=True)

    before = CampaignSchedule.query.filter_by(org_id=org.id).count()

    resp = client.post('/campaigns/new', data={
        'mode': 'schedule',
        'recipient_source': 'paste',
        'name': 'Nope',
        'body': 'nope',
        'pasted_numbers': '0700123456',
        'days': ['mon'],
        'times': ['09:00'],
        'starts_on': '2026-10-10',
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b'Scheduled campaigns send to your contact list' in resp.data

    after = CampaignSchedule.query.filter_by(org_id=org.id).count()
    assert after == before