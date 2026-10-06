"""
Tests for services/pahappa_balance.py.

Mocks EgoSMSClient.balance so no network call is made.
"""
from unittest.mock import patch

import pytest

from app.services import pahappa_balance as pb
from app.services.egosms_client import EgoSMSBalanceResponse


@pytest.fixture(autouse=True)
def reset_cache():
    """Ensure each test starts with a cold cache."""
    pb.invalidate()
    yield
    pb.invalidate()


def test_returns_balance_on_success(app):
    with patch('app.services.pahappa_balance.EgoSMSClient') as MockClient:
        MockClient.return_value.username = 'user'
        MockClient.return_value.balance.return_value = \
            EgoSMSBalanceResponse(ok=True, balance=1500.0)

        result = pb.current()

    assert result['balance'] == 1500
    assert result['error'] is None
    assert result['cached'] is False


def test_cache_hit_on_second_call(app):
    with patch('app.services.pahappa_balance.EgoSMSClient') as MockClient:
        MockClient.return_value.username = 'user'
        MockClient.return_value.balance.return_value = \
            EgoSMSBalanceResponse(ok=True, balance=1500.0)

        pb.current()
        result = pb.current()

    assert result['balance'] == 1500
    assert result['cached'] is True
    # Only one API call despite two invocations
    assert MockClient.return_value.balance.call_count == 1


def test_missing_username_returns_error(app):
    with patch('app.services.pahappa_balance.EgoSMSClient') as MockClient:
        MockClient.return_value.username = ''

        result = pb.current()

    assert result['balance'] is None
    assert 'not configured' in result['error'].lower()


def test_api_failure_returns_error(app):
    with patch('app.services.pahappa_balance.EgoSMSClient') as MockClient:
        MockClient.return_value.username = 'user'
        MockClient.return_value.balance.return_value = \
            EgoSMSBalanceResponse(ok=False, message='Invalid credentials')

        result = pb.current()

    assert result['balance'] is None
    assert 'Invalid credentials' in result['error']


def test_invalidate_forces_refetch(app):
    with patch('app.services.pahappa_balance.EgoSMSClient') as MockClient:
        MockClient.return_value.username = 'user'
        MockClient.return_value.balance.return_value = \
            EgoSMSBalanceResponse(ok=True, balance=1500.0)

        pb.current()
        pb.invalidate()
        result = pb.current()

    assert result['cached'] is False
    assert MockClient.return_value.balance.call_count == 2