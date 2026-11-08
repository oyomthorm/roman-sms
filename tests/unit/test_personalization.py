"""Tests for services/personalization.py and the personalized campaign path."""
import io
import pytest

from app.models import MessageLog
from app.services import wallet as wallet_svc
from app.services import campaigns as svc
from app.services import personalization as perso
from app.services.renderer import substitute_vars, render_personalized
from tests.factories import UserFactory


def _csv(text):
    return io.BytesIO(text.encode('utf-8'))


# ---------- substitute_vars ----------

def test_substitute_vars_replaces_known():
    assert substitute_vars('Hi {{name}}', {'name': 'Joan'}) == 'Hi Joan'


def test_substitute_vars_passes_unknown_through():
    assert substitute_vars('Hi {{name}}', {}) == 'Hi {{name}}'


def test_substitute_vars_handles_none():
    assert substitute_vars('X: {{v}}', {'v': None}) == 'X: '


def test_substitute_vars_case_insensitive():
    assert substitute_vars('{{Name}}', {'name': 'Joan'}) == 'Joan'


# ---------- parse_csv ----------

def test_parse_csv_happy_path():
    text = 'phone,pupil_name,fee_balance\n0700123456,Joan,450000\n0752123456,Peter,300000\n'
    cols, rows, issues = perso.parse_csv(_csv(text))
    assert 'phone' in [c.lower() for c in cols]
    assert len(rows) == 2
    assert rows[0]['phone'] == '256700123456'
    assert rows[0]['vars']['pupil_name'] == 'Joan'
    assert rows[1]['vars']['fee_balance'] == '300000'
    assert issues == []


def test_parse_csv_skips_invalid_rows_with_issues():
    text = 'phone,name\nnot-a-phone,Alice\n0700123456,Bob\n'
    cols, rows, issues = perso.parse_csv(_csv(text))
    assert len(rows) == 1
    assert rows[0]['vars']['name'] == 'Bob'
    assert len(issues) == 1
    assert issues[0]['row_num'] == 2
    assert issues[0]['status'] == 'invalid'


def test_parse_csv_detects_duplicates():
    text = 'phone\n0700123456\n0700123456\n'
    cols, rows, issues = perso.parse_csv(_csv(text))
    assert len(rows) == 1
    assert any(i['status'] == 'duplicate' for i in issues)


def test_parse_csv_detects_phone_alias():
    text = 'mobile_number,pupil\n0700123456,Joan\n'
    cols, rows, issues = perso.parse_csv(_csv(text))
    assert len(rows) == 1
    assert rows[0]['phone'] == '256700123456'


def test_parse_csv_raises_if_no_phone_column():
    text = 'name,fee\nJoan,450000\n'
    with pytest.raises(perso.PersonalizationError):
        perso.parse_csv(_csv(text))


def test_parse_csv_raises_if_all_invalid():
    text = 'phone\nbad1\nbad2\n'
    with pytest.raises(perso.PersonalizationError):
        perso.parse_csv(_csv(text))


# ---------- validate_template ----------

def test_validate_template_rejects_unknown_columns():
    errors = perso.validate_template('Hi {{name}} {{x}}', ['name'])
    assert len(errors) == 1
    assert 'x' in errors[0]


def test_validate_template_accepts_known_columns():
    assert perso.validate_template('Hi {{name}}', ['name']) == []


# ---------- end-to-end create_campaign ----------

def test_create_campaign_personalized_end_to_end(app, db, subscribed_associate):
    org = subscribed_associate
    user = UserFactory(org=org)
    starting = wallet_svc.get_balance(org.id)

    rows = [
        {'phone': '256700000001', 'vars': {'pupil_name': 'Joan', 'fee': '450000'}},
        {'phone': '256700000002', 'vars': {'pupil_name': 'Peter', 'fee': '300000'}},
    ]
    campaign, segs = svc.create_campaign(
        org, name='Fee reminders',
        body='Dear parent, {{pupil_name}} owes {{fee}}.',
        personalized_rows=rows, created_by=user.id)

    assert campaign.total == 2
    # Both messages fit in 1 segment each: prefix + short body.
    assert segs == 2
    assert wallet_svc.get_balance(org.id) == starting - 2

    logs = (MessageLog.query.filter_by(campaign_id=campaign.id)
            .order_by(MessageLog.phone).all())
    assert 'Joan' in logs[0].body and '450000' in logs[0].body
    assert 'Peter' in logs[1].body and '300000' in logs[1].body


def test_personalized_segments_summed_across_rows(app, db, subscribed_associate):
    """Segment count is sum of per-row segments, NOT rows * template segments."""
    org = subscribed_associate
    user = UserFactory(org=org)
    starting = wallet_svc.get_balance(org.id)

    # One short row (1 segment), one row that pushes past 160 chars (2 segments).
    short_vars = {'name': 'X'}
    long_vars = {'name': 'Y' * 200}
    rows = [
        {'phone': '256700000001', 'vars': short_vars},
        {'phone': '256700000002', 'vars': long_vars},
    ]
    campaign, segs = svc.create_campaign(
        org, name='Test', body='Hi {{name}}',
        personalized_rows=rows, created_by=user.id)

    assert campaign.total == 2
    assert segs == 3   # 1 + 2, not 2 * 2 or 2 * 1
    assert wallet_svc.get_balance(org.id) == starting - 3


def test_personalized_skips_opted_out(app, db, subscribed_associate):
    from app.models import OptOut
    org = subscribed_associate
    user = UserFactory(org=org)
    db.session.add(OptOut(phone='256700000099', reason='test'))
    db.session.commit()

    rows = [
        {'phone': '256700000099', 'vars': {'name': 'Blocked'}},
        {'phone': '256700000001', 'vars': {'name': 'OK'}},
    ]
    campaign, segs = svc.create_campaign(
        org, name='Test', body='Hi {{name}}',
        personalized_rows=rows, created_by=user.id)
    assert campaign.total == 1