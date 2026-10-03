import pytest

from app.services import campaign_notifications as cn
from app.services import campaigns as c_svc
from app.services import mailer
from tests.factories import ContactFactory, UserFactory


def _make_complete_campaign(db, org, user, sent=3, failed=0):
    for _ in range(sent + failed):
        ContactFactory(org_id=org.id)
    campaign, _ = c_svc.create_campaign(
        org, name='Test campaign', body='Hi {{name}}',
        created_by=user.id)
    campaign.status = 'complete'
    campaign.sent_count = sent
    campaign.failed_count = failed
    db.session.commit()
    return campaign


@pytest.fixture
def captured_emails(monkeypatch):
    """Replace mailer.send with a capture list."""
    captured = []

    def fake_send(to, subject, body_text, body_html=None):
        captured.append({'to': to, 'subject': subject, 'body': body_text})
        return True

    monkeypatch.setattr(mailer, 'send', fake_send)
    return captured


def test_sends_email_to_creator_and_admins(app, db, subscribed_associate,
                                           captured_emails):
    org = subscribed_associate
    creator = UserFactory(org=org, email='creator@test.local',
                          role='associate_user')
    admin = UserFactory(org=org, email='admin@test.local',
                        role='associate_admin')

    campaign = _make_complete_campaign(db, org, creator)

    n = cn.send_completion_email(campaign.id)
    assert n == 2
    to_addresses = {e['to'] for e in captured_emails}
    assert to_addresses == {'creator@test.local', 'admin@test.local'}


def test_no_duplicate_when_creator_is_also_admin(app, db,
                                                subscribed_associate,
                                                captured_emails):
    org = subscribed_associate
    admin = UserFactory(org=org, email='both@test.local',
                        role='associate_admin')
    campaign = _make_complete_campaign(db, org, admin)

    n = cn.send_completion_email(campaign.id)
    assert n == 1
    assert captured_emails[0]['to'] == 'both@test.local'


def test_disabled_flag_skips_send(app, db, subscribed_associate,
                                  captured_emails):
    app.config['EMAIL_ON_CAMPAIGN_COMPLETE'] = False
    org = subscribed_associate
    user = UserFactory(org=org)
    campaign = _make_complete_campaign(db, org, user)

    n = cn.send_completion_email(campaign.id)
    assert n == 0
    assert captured_emails == []


def test_skips_non_complete_campaign(app, db, subscribed_associate,
                                     captured_emails):
    org = subscribed_associate
    user = UserFactory(org=org)
    ContactFactory(org_id=org.id)
    campaign, _ = c_svc.create_campaign(
        org, name='T', body='Hi', created_by=user.id)
    # campaign.status is 'queued', not 'complete'

    n = cn.send_completion_email(campaign.id)
    assert n == 0
    assert captured_emails == []


def test_skips_missing_campaign(app, db, captured_emails):
    n = cn.send_completion_email(99999)
    assert n == 0


def test_body_contains_report_url(app, db, subscribed_associate,
                                   captured_emails):
    app.config['PUBLIC_BASE_URL'] = 'https://example.test'
    org = subscribed_associate
    user = UserFactory(org=org)
    campaign = _make_complete_campaign(db, org, user)

    cn.send_completion_email(campaign.id)
    body = captured_emails[0]['body']
    assert f'https://example.test/campaigns/{campaign.id}' in body
    assert 'Recipients: 3' in body
    assert 'Sent:       3' in body


def test_mailer_failure_does_not_raise(app, db, subscribed_associate,
                                        monkeypatch):
    def failing_send(*a, **kw):
        raise RuntimeError('smtp down')

    monkeypatch.setattr(mailer, 'send', failing_send)
    org = subscribed_associate
    user = UserFactory(org=org)
    campaign = _make_complete_campaign(db, org, user)

    # Should swallow and return 0
    n = cn.send_completion_email(campaign.id)
    assert n == 0