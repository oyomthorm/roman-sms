"""
EgoSMS / Pahappa Comms API client.

Confirmed from the developer docs:

  Endpoint (live):    POST https://comms.egosms.co/api/v1/json/
  Endpoint (sandbox): POST https://comms-test.pahappa.net/api/v1/json/
  Content-Type:       application/json

  Request shape:
    {
      "method": "SendSms",
      "userdata": {"username": ..., "password": ...},
      "msgdata": [
        {"number": "256…", "message": "…",
         "senderid": "…", "priority": 0..4}
      ]
    }

  Response (always HTTP 200, even on failure):
    Success: {"Status": "OK", "Cost": <num>, "MsgFollowUpUniqueCode": "…"}
    Failure: {"Status": "Failed", "Message": "<reason>"}

  Balance request:
    {"method": "Balance",
     "userdata": {...},
     "walletType": "local" | "international"}   # omit field for local

  Balance response:
    {"Status": "OK", "Balance": <num>}
    {"Status": "Failed", "Message": "…"}

  Max 1000 messages per request. Priority 0 = most urgent.
"""
import logging

import requests
from flask import current_app

log = logging.getLogger(__name__)


JSON_ENDPOINT = 'https://comms.egosms.co/api/v1/json/'
SANDBOX_ENDPOINT = 'https://comms-test.pahappa.net/api/v1/json/'

MAX_BATCH = 1000


class EgoSMSResponse:
    """Parsed response from a send request."""
    def __init__(self, ok, status, message=None, cost=None,
                 follow_up_code=None, raw=None):
        self.ok = ok
        self.status = status
        self.message = message
        self.cost = cost
        self.follow_up_code = follow_up_code
        self.raw = raw

    def __repr__(self):
        return (f'<EgoSMSResponse ok={self.ok} status={self.status} '
                f'cost={self.cost} code={self.follow_up_code}>')


class EgoSMSBalanceResponse:
    """Parsed response from a balance request."""
    def __init__(self, ok, balance=None, message=None, raw=None):
        self.ok = ok
        self.balance = balance
        self.message = message
        self.raw = raw

    def __repr__(self):
        return f'<EgoSMSBalanceResponse ok={self.ok} balance={self.balance}>'


class EgoSMSClient:
    def __init__(self):
        c = current_app.config
        self.username = c.get('EGOSMS_USERNAME') or ''
        self.password = c.get('EGOSMS_PASSWORD') or ''
        self.sender = c.get('EGOSMS_DEFAULT_SENDER', 'ROMANSMS')
        self.timeout = c.get('EGOSMS_TIMEOUT', 20)
        self.sandbox = c.get('EGOSMS_SANDBOX', False)
        self.endpoint = SANDBOX_ENDPOINT if self.sandbox else JSON_ENDPOINT

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    def send_batch(self, messages):
        """
        messages: list of {'number', 'message'} with optional 'senderid'
                  and 'priority'.

        Returns EgoSMSResponse. Never raises on network error — returns
        ok=False so the caller can mark failed and refund.
        """
        if not messages:
            return EgoSMSResponse(ok=True, status='OK',
                                  message='empty batch', cost=0)

        if len(messages) > MAX_BATCH:
            log.warning('Batch of %s exceeds API max of %s; truncating.',
                        len(messages), MAX_BATCH)
            messages = messages[:MAX_BATCH]

        payload = {
            'method': 'SendSms',
            'userdata': {
                'username': self.username,
                'password': self.password,
            },
            'msgdata': [self._build_message(m) for m in messages],
        }

        try:
            r = requests.post(
                self.endpoint,
                json=payload,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'},
            )
        except requests.RequestException as e:
            log.error('EgoSMS network error: %s', e)
            return EgoSMSResponse(ok=False, status='NetworkError',
                                  message=str(e))

        try:
            data = r.json()
        except ValueError:
            log.error('EgoSMS invalid JSON. status=%s body=%s',
                      r.status_code, r.text[:500])
            return EgoSMSResponse(ok=False, status='InvalidResponse',
                                  message=f'HTTP {r.status_code}')

        return self._parse_send(data)

    # ------------------------------------------------------------------
    # Balance
    # ------------------------------------------------------------------

    def balance(self, wallet_type=None):
        """
        Query the current wallet balance.

        wallet_type: None, 'local', or 'international'.
        Omit the field to check the local wallet. Sending it as null is
        rejected by the API, which is why we only add it when set.
        """
        payload = {
            'method': 'Balance',
            'userdata': {
                'username': self.username,
                'password': self.password,
            },
        }
        if wallet_type in ('local', 'international'):
            payload['walletType'] = wallet_type

        try:
            r = requests.post(self.endpoint, json=payload,
                              timeout=self.timeout,
                              headers={'Content-Type': 'application/json'})
        except requests.RequestException as e:
            log.error('EgoSMS balance network error: %s', e)
            return EgoSMSBalanceResponse(ok=False, message=str(e))

        try:
            data = r.json()
        except ValueError:
            log.error('EgoSMS balance invalid JSON: %s', r.text[:300])
            return EgoSMSBalanceResponse(ok=False,
                                         message='invalid response')

        return self._parse_balance(data)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_message(self, m):
        return {
            'number': self._normalise_number(m['number']),
            'message': m['message'],
            'senderid': m.get('senderid') or self.sender,
            'priority': m.get('priority', 1),
        }

    @staticmethod
    def _normalise_number(number):
        """
        Docs say international format, no leading + or 0.
        Our phones.normalize_ug already returns 256XXXXXXXXX, but be safe.
        """
        n = str(number or '').strip()
        if n.startswith('+'):
            n = n[1:]
        elif n.startswith('0') and len(n) == 10:
            n = '256' + n[1:]
        return n

    def _parse_send(self, data):
        """
        Live API uses capitalized keys (Status, Cost, MsgFollowUpUniqueCode).
        Older docs used lowercase. Accept both.
        """
        if not isinstance(data, dict):
            return EgoSMSResponse(
                ok=False, status='InvalidResponse',
                message=f'Unexpected type: {type(data).__name__}',
                raw=data)

        status = str(data.get('Status') or data.get('status') or '').strip()

        if status.lower() == 'ok':
            return EgoSMSResponse(
                ok=True,
                status='OK',
                cost=self._coerce_float(
                    data.get('Cost') if 'Cost' in data else data.get('cost')),
                follow_up_code=(data.get('MsgFollowUpUniqueCode')
                                or data.get('messageFollowUpCode')
                                or data.get('followUpCode')),
                raw=data,
            )

        if status.lower() == 'failed':
            return EgoSMSResponse(
                ok=False,
                status='Failed',
                message=(data.get('Message') or data.get('message')
                         or 'Unknown failure'),
                raw=data,
            )

        return EgoSMSResponse(
            ok=False,
            status='UnknownStatus',
            message=f'Unrecognised response: {str(data)[:200]}',
            raw=data,
        )

    def _parse_balance(self, data):
        if not isinstance(data, dict):
            return EgoSMSBalanceResponse(ok=False,
                                         message='unexpected shape',
                                         raw=data)

        status = str(data.get('Status') or data.get('status') or '').strip()

        if status.lower() == 'ok':
            raw_balance = (data.get('Balance')
                           if 'Balance' in data else data.get('balance'))
            return EgoSMSBalanceResponse(
                ok=True,
                balance=self._coerce_float(raw_balance),
                raw=data,
            )

        return EgoSMSBalanceResponse(
            ok=False,
            message=(data.get('Message') or data.get('message')
                     or 'Failed'),
            raw=data,
        )

    @staticmethod
    def _coerce_float(raw):
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None