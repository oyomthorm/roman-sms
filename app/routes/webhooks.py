"""
Inbound webhooks from Pahappa Comms.

Currently only the transaction-status webhook — called when the network
reports delivery outcome for a message.

Security:
  - URL contains an unguessable token (WEBHOOK_TOKEN from config)
  - Token mismatch → 404, so we do not reveal the endpoint exists
  - Responds 200 immediately to any well-formed payload
"""
import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from app.extensions import db, csrf
from app.models import MessageLog


log = logging.getLogger('roman.webhooks')
webhooks_bp = Blueprint('webhooks', __name__)


def _parse_iso8601(value):
    """
    Parse the deliveryDate field. Pahappa sends ISO 8601 with a Z
    suffix (e.g. "2026-08-05T08:58:23.679Z"). Returns a naive UTC
    datetime or None.

    Every DateTime column in the schema is naive UTC — set from
    datetime.utcnow(). Converting to server-local time here would
    make delivered_at the only column that isn't UTC, breaking
    dashboard filters that compare it against utcnow().
    """
    if not value or not isinstance(value, str):
        return None
    try:
        cleaned = (value.replace('Z', '+00:00')
                   if value.endswith('Z') else value)
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        log.warning('Could not parse deliveryDate %r', value)
        return None
    

@webhooks_bp.route('/transaction-status/<token>', methods=['POST'])
@csrf.exempt
def transaction_status(token):
    """
    Receive a delivery report from Pahappa.

    Payload:
      {
        "MsgFollowUpUniqueCode": "…",
        "number": "256…",
        "Status": "Success",
        "deliveryDate": "2026-08-05T08:58:23.679Z"
      }

    We match on BOTH the follow-up code and the phone number, because a
    single batch shares one follow-up code across many numbers.

    Always respond 200 for well-formed payloads so Pahappa does not
    retry. Log and move on if we cannot match — it means the message
    was sent by someone else's system, or the batch has been purged.
    """
    expected = current_app.config.get('WEBHOOK_TOKEN')
    if not expected or token != expected:
        # Do not leak that this endpoint exists.
        return jsonify({'ok': False}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        log.warning('Webhook payload was not JSON: %r', request.data[:200])
        return jsonify({'ok': False, 'error': 'invalid payload'}), 400

    follow_up = (data.get('MsgFollowUpUniqueCode') or '').strip()
    number = (data.get('number') or '').strip()
    raw_status = (data.get('Status') or '').strip()
    delivery_date = _parse_iso8601(data.get('deliveryDate'))

    if not follow_up or not number or not raw_status:
        log.warning('Webhook payload missing fields: %s', data)
        return jsonify({'ok': False, 'error': 'missing fields'}), 400

    # Normalise the number the same way the client does, in case Pahappa
    # ever sends a leading + or 0.
    if number.startswith('+'):
        number = number[1:]

    # Find matching message(s). We expect one, but a resend could
    # produce two, and both should be updated.
    rows = (MessageLog.query
            .filter_by(provider_ref=follow_up, phone=number)
            .all())

    if not rows:
        log.info('Webhook: no MessageLog matched code=%s number=%s',
                 follow_up, number)
        # 200 so Pahappa does not retry — this is not their problem.
        return jsonify({'ok': True, 'matched': 0})

    new_status = 'delivered' if raw_status.lower() == 'success' \
        else 'delivery_failed'

    updated = 0
    for m in rows:
        # Only advance if we are still in 'sent'. Do not overwrite a
        # terminal state, and do not revive a failed one.
        if m.status == 'sent':
            m.status = new_status
            m.delivery_status_raw = raw_status[:40]
            m.delivered_at = delivery_date
            updated += 1

    db.session.commit()

    log.info('Webhook: code=%s number=%s raw=%s → %s (%s rows)',
             follow_up, number, raw_status, new_status, updated)

    return jsonify({'ok': True, 'matched': updated}), 200