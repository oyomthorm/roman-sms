"""
Live Pahappa wholesale balance.

The master wallet is a snapshot: it records what Pahappa's balance was
at seed time, plus any internal adjustments. It does not move when
associates send, because their sends debit Pahappa directly, not the
master wallet.

This service fetches the real Pahappa balance, cached for 5 minutes
so dashboard renders don't hammer the API. Call invalidate() to force
a fresh fetch.
"""
import logging
import time
from threading import Lock

from app.services.egosms_client import EgoSMSClient


log = logging.getLogger('roman.pahappa_balance')


CACHE_TTL_SECONDS = 300   # 5 minutes

_cache = {'balance': None, 'error': None, 'fetched_at': 0}
_lock = Lock()


def current():
    """
    Return the current Pahappa balance.

    Returns a dict:
        balance     — int or None
        error       — str or None  (populated if the fetch failed)
        fetched_at  — unix timestamp
        cached      — True if this came from the cache
    """
    with _lock:
        now = time.time()

        if _cache['fetched_at'] and (now - _cache['fetched_at']) < CACHE_TTL_SECONDS:
            return {
                'balance': _cache['balance'],
                'error': _cache['error'],
                'fetched_at': _cache['fetched_at'],
                'cached': True,
            }

        try:
            client = EgoSMSClient()
        except Exception as e:
            _cache.update({'balance': None,
                           'error': f'client init failed: {e}',
                           'fetched_at': now})
            return {
                'balance': None,
                'error': _cache['error'],
                'fetched_at': now,
                'cached': False,
            }

        if not client.username:
            _cache.update({'balance': None,
                           'error': 'EGOSMS_USERNAME not configured',
                           'fetched_at': now})
            return {
                'balance': None,
                'error': _cache['error'],
                'fetched_at': now,
                'cached': False,
            }

        try:
            resp = client.balance()
        except Exception as e:
            _cache.update({'balance': None,
                           'error': f'query failed: {e}',
                           'fetched_at': now})
            return {
                'balance': None,
                'error': _cache['error'],
                'fetched_at': now,
                'cached': False,
            }

        if not resp.ok or resp.balance is None:
            _cache.update({'balance': None,
                           'error': resp.message or 'query failed',
                           'fetched_at': now})
            return {
                'balance': None,
                'error': _cache['error'],
                'fetched_at': now,
                'cached': False,
            }

        _cache.update({'balance': int(resp.balance),
                       'error': None,
                       'fetched_at': now})
        return {
            'balance': int(resp.balance),
            'error': None,
            'fetched_at': now,
            'cached': False,
        }


def invalidate():
    """Force the next call to current() to hit the API."""
    with _lock:
        _cache['fetched_at'] = 0