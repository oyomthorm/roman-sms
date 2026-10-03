from app.services import optout_links


def test_token_round_trip(app):
    token = optout_links.make_token('256700123456')
    assert optout_links.read_token(token) == '256700123456'


def test_invalid_token_returns_none(app):
    assert optout_links.read_token('garbage') is None


def test_url_none_when_base_url_missing(app):
    app.config['PUBLIC_BASE_URL'] = ''
    assert optout_links.optout_url('256700123456') is None


def test_url_includes_base(app):
    app.config['PUBLIC_BASE_URL'] = 'https://example.test'
    url = optout_links.optout_url('256700123456')
    assert url.startswith('https://example.test/opt-out/')