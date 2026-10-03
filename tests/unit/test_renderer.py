"""
Tests for services/renderer.py.

Covers:
  - placeholder substitution ({{name}}, {{phone}}, unknown)
  - brand prefix application
  - end-to-end render()
  - the ADR-017 behaviour: no opt-out link appended
  - segment arithmetic
"""
import pytest

from app.extensions import db
from app.models import Contact
from app.services import renderer


@pytest.fixture
def contact(db, associate_org):
    c = Contact(
        org_id=associate_org.id,
        phone='256700123456',
        name='Alice Example',
    )
    db.session.add(c)
    db.session.commit()
    return c


# ---------------------------------------------------------------------------
# substitute
# ---------------------------------------------------------------------------

def test_substitute_name(app, contact):
    assert renderer.substitute('Hi {{name}}', contact) == 'Hi Alice Example'


def test_substitute_phone(app, contact):
    assert renderer.substitute('Call {{phone}}', contact) == 'Call 256700123456'


def test_substitute_both(app, contact):
    assert (renderer.substitute('{{name}} / {{phone}}', contact)
            == 'Alice Example / 256700123456')


def test_substitute_case_insensitive(app, contact):
    assert renderer.substitute('Hi {{NAME}}', contact) == 'Hi Alice Example'


def test_substitute_whitespace_inside(app, contact):
    assert renderer.substitute('Hi {{ name }}', contact) == 'Hi Alice Example'


def test_substitute_unknown_placeholder_left_alone(app, contact):
    assert renderer.substitute('Hi {{unknown}}', contact) == 'Hi {{unknown}}'


def test_substitute_name_missing_is_empty(app, db, associate_org):
    c = Contact(org_id=associate_org.id, phone='256700999999', name=None)
    db.session.add(c)
    db.session.commit()
    assert renderer.substitute('Hi {{name}}!', c) == 'Hi !'


def test_substitute_no_placeholder(app, contact):
    assert renderer.substitute('Plain body', contact) == 'Plain body'


# ---------------------------------------------------------------------------
# with_prefix
# ---------------------------------------------------------------------------

def test_with_prefix(app, associate_org):
    # conftest sets associate_org.brand_name = 'Kampalafit'
    assert renderer.with_prefix(associate_org, 'Hi') == 'Kampalafit: Hi'


# ---------------------------------------------------------------------------
# render — the composed function used by campaigns
# ---------------------------------------------------------------------------

def test_render_applies_prefix_and_substitution(app, associate_org, contact):
    body = renderer.render(associate_org, 'Hi {{name}}', contact)
    assert body == 'Kampalafit: Hi Alice Example'


def test_render_does_not_append_optout(app, associate_org, contact):
    """
    ADR-017: opt-out link removed from outbound messages. render()
    must not append the URL even when PUBLIC_BASE_URL is set.
    """
    app.config['PUBLIC_BASE_URL'] = 'https://example.test'
    body = renderer.render(associate_org, 'Hi {{name}}', contact)
    assert 'opt-out' not in body.lower()
    assert 'opt out' not in body.lower()
    assert 'https://example.test' not in body
    assert body == 'Kampalafit: Hi Alice Example'


def test_render_does_not_append_optout_when_base_url_absent(
        app, associate_org, contact):
    app.config['PUBLIC_BASE_URL'] = ''
    body = renderer.render(associate_org, 'Hi', contact)
    assert 'opt-out' not in body.lower()


# ---------------------------------------------------------------------------
# segments
# ---------------------------------------------------------------------------

def test_segments_empty_body_is_one(app):
    # min 1 even for empty input — an empty SMS still costs one segment
    assert renderer.segments('') == 1


def test_segments_under_160_is_one(app):
    assert renderer.segments('a' * 160) == 1


def test_segments_161_is_two(app):
    assert renderer.segments('a' * 161) == 2


def test_segments_320_is_two(app):
    assert renderer.segments('a' * 320) == 2


def test_segments_321_is_three(app):
    assert renderer.segments('a' * 321) == 3


def test_segments_respects_config(app):
    app.config['SMS_SEGMENT_CHARS'] = 70
    assert renderer.segments('a' * 70) == 1
    assert renderer.segments('a' * 71) == 2