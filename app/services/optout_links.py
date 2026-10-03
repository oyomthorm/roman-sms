"""
Signed opt-out tokens. Included in every SMS body so recipients can click
a link to opt out without needing to reply (the master sender ID is
outbound-only).
"""
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app

TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 180  # 6 months


def _serializer():
    return URLSafeTimedSerializer(
        current_app.config['SECRET_KEY'],
        salt='optout',
    )


def make_token(phone):
    return _serializer().dumps(phone)


def read_token(token):
    """Returns phone or None if invalid/expired."""
    try:
        return _serializer().loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


def optout_url(phone):
    base = current_app.config.get('PUBLIC_BASE_URL', '')
    if not base:
        # No public URL configured — do not generate broken links.
        return None
    return f"{base.rstrip('/')}/opt-out/{make_token(phone)}"