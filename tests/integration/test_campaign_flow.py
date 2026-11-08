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

# ---------------------------------------------------------------------------
# Personalized CSV recipient source (#33 Session B - route wiring)
# ---------------------------------------------------------------------------


def _csv_upload(text):
    """Build a Flask test-client file tuple from a string."""
    import io
    return (io.BytesIO(text.encode('utf-8')), 'recipients.csv')


def test_personalized_preview_returns_json(client, app, db,
                                           associate_admin,
                                           subscribed_associate):
    """The preview endpoint validates CSV + template and returns JSON."""
    client.post('/login', data={
        'email': associate_admin.email, 'password': 'assocpass',
    }, follow_redirects=True)

    csv_text = 'phone,pupil_name,fee\n' \
               '0700123456,Joan,450000\n' \
               '0752123456,Peter,300000\n'

    resp = client.post(
        '/campaigns/personalized/preview',
        data={
            'personalized_body': 'Dear parent, {{pupil_name}} owes {{fee}}.',
            'personalized_csv': _csv_upload(csv_text),
        },
        content_type='multipart/form-data',
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['ok'] is True
    assert payload['row_count'] == 2
    assert payload['total_segments'] == 2
    assert len(payload['preview']) == 2
    assert 'phone' in payload['columns_all']
    assert 'pupil_name' in payload['columns']
    assert payload['errors'] == []


def test_personalized_preview_rejects_unknown_column(client, app, db,
                                                     associate_admin,
                                                     subscribed_associate):
    """Template referencing a column not in the CSV returns errors[]."""
    client.post('/login', data={
        'email': associate_admin.email, 'password': 'assocpass',
    }, follow_redirects=True)

    csv_text = 'phone,pupil_name\n0700123456,Joan\n'
    resp = client.post(
        '/campaigns/personalized/preview',
        data={
            'personalized_body': 'Hi {{missing_column}}',
            'personalized_csv': _csv_upload(csv_text),
        },
        content_type='multipart/form-data',
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['ok'] is True
    assert len(payload['errors']) == 1
    assert 'missing_column' in payload['errors'][0]


def test_personalized_campaign_via_route(client, app, db,
                                         associate_admin,
                                         subscribed_associate):
    """POST a personalized campaign -> per-row MessageLog bodies."""
    from app.models import Campaign, MessageLog
    from app.services import wallet as wallet_svc

    org = subscribed_associate
    client.post('/login', data={
        'email': associate_admin.email, 'password': 'assocpass',
    }, follow_redirects=True)

    starting = wallet_svc.get_balance(org.id)

    csv_text = 'phone,pupil_name,fee\n' \
               '0700123456,Joan,450000\n' \
               '0752123456,Peter,300000\n'

    resp = client.post(
        '/campaigns/new',
        data={
            'mode': 'now',
            'recipient_source': 'personalized',
            'name': 'Fee reminders',
            'personalized_body': 'Dear parent, {{pupil_name}} owes {{fee}}.',
            'personalized_csv': _csv_upload(csv_text),
        },
        content_type='multipart/form-data',
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert '/campaigns/' in resp.headers['Location']

    campaign = (Campaign.query
                .filter_by(org_id=org.id)
                .order_by(Campaign.id.desc())
                .first())
    assert campaign is not None
    assert campaign.name == 'Fee reminders'
    assert campaign.total == 2
    assert wallet_svc.get_balance(org.id) == starting - 2

    logs = (MessageLog.query
            .filter_by(campaign_id=campaign.id)
            .order_by(MessageLog.phone)
            .all())
    assert len(logs) == 2
    # Rendered bodies differ per row - that's the whole point.
    assert 'Joan' in logs[0].body and '450000' in logs[0].body
    assert 'Peter' in logs[1].body and '300000' in logs[1].body


def test_personalized_rejects_schedule(client, app, db,
                                       associate_admin,
                                       subscribed_associate):
    """mode=schedule + recipient_source=personalized is refused."""
    from app.models import CampaignSchedule

    client.post('/login', data={
        'email': associate_admin.email, 'password': 'assocpass',
    }, follow_redirects=True)

    before = CampaignSchedule.query.filter_by(
        org_id=subscribed_associate.id).count()

    csv_text = 'phone\n0700123456\n'
    resp = client.post(
        '/campaigns/new',
        data={
            'mode': 'schedule',
            'recipient_source': 'personalized',
            'name': 'Nope',
            'body': 'Hi',
            'personalized_csv': _csv_upload(csv_text),
            'scheduled_times': ['2026-12-01T09:00'],
        },
        content_type='multipart/form-data',
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert b'Scheduled campaigns send to your contact list' in resp.data

    after = CampaignSchedule.query.filter_by(
        org_id=subscribed_associate.id).count()
    assert after == before


def test_personalized_rejects_missing_csv(client, app, db,
                                          associate_admin,
                                          subscribed_associate):
    """recipient_source=personalized without a CSV -> flash, no campaign."""
    from app.models import Campaign

    client.post('/login', data={
        'email': associate_admin.email, 'password': 'assocpass',
    }, follow_redirects=True)

    before = Campaign.query.filter_by(
        org_id=subscribed_associate.id).count()

    resp = client.post('/campaigns/new', data={
        'mode': 'now',
        'recipient_source': 'personalized',
        'name': 'No file',
        'body': 'Hi',
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b'upload a CSV' in resp.data

    after = Campaign.query.filter_by(
        org_id=subscribed_associate.id).count()
    assert after == before