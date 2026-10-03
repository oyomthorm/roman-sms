"""
Password reset via signed tokens. No DB table needed — the token carries
a timestamp and is validated against a per-purpose max age. The user's
current password hash is mixed into the salt so a token cannot be reused
after a successful reset.

Two purposes share this module:
  reset   — self-service forgot-password. 1 hour.
  welcome — the link sent when a signup is approved. 24 hours, because
            a new associate may not check their inbox immediately.
"""
from itsdangerous import (URLSafeTimedSerializer, BadSignature,
                          SignatureExpired)
from flask import current_app

RESET_MAX_AGE_SECONDS = 60 * 60              # 1 hour
WELCOME_MAX_AGE_SECONDS = 24 * 60 * 60       # 24 hours

_PURPOSE_MAX_AGE = {
    'reset': RESET_MAX_AGE_SECONDS,
    'welcome': WELCOME_MAX_AGE_SECONDS,
}


def _serializer(user, purpose):
    salt = f'pwreset:{purpose}:{user.password_hash[-8:]}'
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'],
                                  salt=salt)


def make_token(user, purpose='reset'):
    if purpose not in _PURPOSE_MAX_AGE:
        raise ValueError(f'Unknown reset purpose: {purpose}')
    return _serializer(user, purpose).dumps(user.id)


def read_token(user, token, purpose='reset'):
    max_age = _PURPOSE_MAX_AGE.get(purpose)
    if max_age is None:
        return False
    try:
        uid = _serializer(user, purpose).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return False
    return uid == user.id