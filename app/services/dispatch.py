"""
Roman SMS — dispatch service.

Owns the send loop. Called by worker.py, and by tests with the EgoSMS
client stubbed.

Responsibilities:
  - claim pending jobs from send_queue atomically
  - requeue jobs that got stuck in 'processing'
  - process a job: batch messages, send, mark outcomes, refund failures,
    store provider follow-up code and cost
  - never leak credits: debit happens in services.campaigns before dispatch

Contract with services.campaigns:
  - every SendQueue row has a matching Campaign in status 'queued'
  - every pending MessageLog belongs to exactly one campaign
  - wallet debits are already committed before the worker sees the job
"""
import logging
import time
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy import text

from app.extensions import db
from app.models import Campaign, MessageLog, SendQueue, Organization
from app.services import wallet as wallet_svc
from app.services import ratelimit
from app.services.egosms_client import EgoSMSClient, EgoSMSResponse


log = logging.getLogger('roman.dispatch')


# --------------------------------------------------------------------------
# Job claiming
# --------------------------------------------------------------------------

def claim_jobs(limit=5):
    """
    Atomically claim up to `limit` pending jobs whose run_after has passed.

    Uses SELECT ... FOR UPDATE SKIP LOCKED on Postgres so multiple workers
    never claim the same job. Falls back to a plain SELECT on SQLite, which
    is safe only for a single worker (dev).

    Returns a list of SendQueue ids now marked 'processing'.
    """
    now = datetime.utcnow()
    log.debug('claim_jobs called, limit=%s, now=%s', limit, now)

    ids = []
    try:
        sql = text("""
            SELECT id FROM send_queue
            WHERE status = 'pending' AND run_after <= :now
            ORDER BY id
            LIMIT :lim
            FOR UPDATE SKIP LOCKED
        """)
        rows = db.session.execute(
            sql, {'lim': limit, 'now': now}
        ).fetchall()
        ids = [r[0] for r in rows]
    except Exception as e:
        log.debug('FOR UPDATE SKIP LOCKED unavailable (%s); '
                  'falling back to plain select.', e)
        db.session.rollback()
        try:
            rows = db.session.execute(text("""
                SELECT id FROM send_queue
                WHERE status = 'pending' AND run_after <= :now
                ORDER BY id
                LIMIT :lim
            """), {'lim': limit, 'now': now}).fetchall()
            ids = [r[0] for r in rows]
        except Exception as e2:
            log.error('claim_jobs fallback failed: %s', e2)
            db.session.rollback()
            return []

    if not ids:
        return []

    try:
        (SendQueue.query
         .filter(SendQueue.id.in_(ids), SendQueue.status == 'pending')
         .update({'status': 'processing',
                  'locked_at': datetime.utcnow(),
                  'attempts': SendQueue.attempts + 1},
                 synchronize_session=False))
        db.session.commit()
    except Exception as e:
        log.error('claim_jobs update failed: %s', e)
        db.session.rollback()
        return []

    return ids


def requeue_stuck(max_age_minutes=15):
    """
    Return any job stuck in 'processing' for longer than max_age_minutes
    back to 'pending' so it can be retried. Covers worker crashes mid-send.
    """
    cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
    stuck = (SendQueue.query
             .filter(SendQueue.status == 'processing',
                     SendQueue.locked_at < cutoff)
             .all())
    if not stuck:
        return 0

    for job in stuck:
        log.warning('Requeuing stuck job %s (locked at %s, attempts=%s)',
                    job.id, job.locked_at, job.attempts)
        job.status = 'pending'
        job.run_after = datetime.utcnow()
        job.locked_at = None
        job.last_error = 'requeued after timeout'
    db.session.commit()
    return len(stuck)


# --------------------------------------------------------------------------
# Job processing
# --------------------------------------------------------------------------

def process_job(job_id):
    """
    Process one claimed job to completion.

    Idempotent per-message: only 'pending' MessageLog rows are sent, so a
    retry after a crash resumes rather than duplicates.
    """
    job = db.session.get(SendQueue, job_id)
    if not job:
        log.warning('process_job: job %s not found', job_id)
        return

    campaign = db.session.get(Campaign, job.campaign_id)
    org = db.session.get(Organization, job.org_id)

    if not campaign or not org:
        log.error('process_job: orphan job %s (campaign=%s org=%s)',
                  job_id, job.campaign_id, job.org_id)
        job.status = 'failed'
        job.last_error = 'campaign or org missing'
        job.finished_at = datetime.utcnow()
        db.session.commit()
        return

    log.info('Processing job %s: campaign=%s org=%s status=%s',
             job_id, campaign.id, org.id, campaign.status)

    # If the campaign was cancelled before we started, mark the job done.
    if campaign.status == 'cancelled':
        log.info('Campaign %s already cancelled; skipping job %s',
                 campaign.id, job_id)
        job.status = 'failed'
        job.last_error = 'campaign cancelled'
        job.finished_at = datetime.utcnow()
        db.session.commit()
        return

    # Suspension is re-checked here, not just at campaign creation.
    if org.status != 'active':
        log.warning('Org %s is %s; cancelling campaign %s',
                    org.id, org.status, campaign.id)
        campaign.status = 'cancelled'
        campaign.completed_at = datetime.utcnow()
        (MessageLog.query
         .filter_by(campaign_id=campaign.id, status='pending')
         .update({'status': 'cancelled'}, synchronize_session=False))
        job.status = 'failed'
        job.last_error = 'org suspended'
        job.finished_at = datetime.utcnow()
        db.session.commit()
        return

    # Entering send state.
    campaign.status = 'sending'
    db.session.commit()

    client = EgoSMSClient()
    batch_size = current_app.config['WORKER_BATCH_SIZE']
    interval = current_app.config['WORKER_SEND_INTERVAL']

    try:
        while True:
            # ---- Rate limit gate ----
            status = ratelimit.check(org)

            if status.remaining_day <= 0:
                log.info('Campaign %s paused: org %s hit daily limit '
                         '(%s/%s). Requeuing for later.',
                         campaign.id, org.id, status.max_day, status.max_day)
                campaign.status = 'queued'
                job.status = 'pending'
                job.locked_at = None
                job.run_after = datetime.utcnow() + timedelta(hours=1)
                job.last_error = 'daily rate limit reached'
                db.session.commit()
                return

            if status.remaining_minute <= 0:
                log.debug('Campaign %s paused: minute limit reached '
                          '(%s/%s). Sleeping.',
                          campaign.id, status.max_minute, status.max_minute)
                time.sleep(min(interval or 1.0, 2.0))
                continue

            # Never take more than the minute budget allows.
            this_batch = min(batch_size, status.remaining_minute)

            pending = (MessageLog.query
                       .filter_by(campaign_id=campaign.id, status='pending')
                       .order_by(MessageLog.id)
                       .limit(this_batch)
                       .all())
            if not pending:
                break

            # Re-check suspension between batches.
            db.session.refresh(org)
            if org.status != 'active':
                log.warning('Org %s suspended mid-campaign %s; stopping.',
                            org.id, campaign.id)
                (MessageLog.query
                 .filter_by(campaign_id=campaign.id, status='pending')
                 .update({'status': 'cancelled'}, synchronize_session=False))
                campaign.status = 'cancelled'
                campaign.completed_at = datetime.utcnow()
                job.status = 'failed'
                job.last_error = 'org suspended mid-campaign'
                job.finished_at = datetime.utcnow()
                db.session.commit()
                return

            payload = [{'number': m.phone, 'message': m.body}
                       for m in pending]

            resp = client.send_batch(payload)
            sent, failed, refunded = _apply_response(pending, resp)

            campaign.sent_count = (campaign.sent_count or 0) + sent
            campaign.failed_count = (campaign.failed_count or 0) + failed
            db.session.commit()

            log.info('Campaign %s: batch sent=%s failed=%s '
                     '(totals sent=%s failed=%s of %s, minute budget %s/%s)',
                     campaign.id, sent, failed,
                     campaign.sent_count, campaign.failed_count,
                     campaign.total,
                     status.remaining_minute - sent, status.max_minute)

            if failed:
                _refund_failed(org.id, campaign.id, failed)

            if interval:
                time.sleep(interval)

        # Loop finished — all pending rows are handled.
        campaign.status = 'complete'
        campaign.completed_at = datetime.utcnow()
        job.status = 'done'
        job.finished_at = datetime.utcnow()
        db.session.commit()
        log.info('Campaign %s complete. sent=%s failed=%s',
                 campaign.id, campaign.sent_count, campaign.failed_count)

    except Exception as e:
        # Leave the job in 'processing' so requeue_stuck() retries it.
        log.exception('Job %s failed while processing campaign %s',
                      job_id, campaign.id)
        try:
            job.last_error = str(e)[:1000]
            db.session.commit()
        except Exception:
            db.session.rollback()
        raise


# --------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------

def _refund_failed(org_id, campaign_id, failed_count):
    """Refund credits for messages that failed to send."""
    try:
        wallet_svc.credit(
            org_id, failed_count,
            reason='refund',
            reference=f'campaign:{campaign_id}',
            note='Auto-refund for failed sends',
        )
        db.session.commit()
        log.info('Refunded %s credit(s) to org %s for campaign %s',
                 failed_count, org_id, campaign_id)
    except Exception as e:
        db.session.rollback()
        log.error('Refund failed for campaign %s: %s', campaign_id, e)


def _apply_response(logs, resp):
    """
    Map an EgoSMSResponse onto the given MessageLog rows.

    Returns (sent_count, failed_count, refund_count).

    The API returns one status per batch — every message in the batch
    either succeeded or failed together. That is why refund_count equals
    failed_count for a batch failure; they are kept separate so a future
    partial-success API can update only one of them.
    """
    now = datetime.utcnow()

    # Backward tolerance: coerce legacy dicts and lists.
    if not isinstance(resp, EgoSMSResponse):
        resp = _legacy_coerce(resp)

    if not resp.ok:
        reason = (resp.message or resp.status or 'unknown error')[:500]
        for m in logs:
            m.status = 'failed'
            m.api_response = reason
        db.session.flush()
        return 0, len(logs), len(logs)

    # Success: attach follow-up code and per-message cost.
    batch_code = (resp.follow_up_code or '')[:120]
    per_message_cost = None
    if resp.cost is not None and logs:
        try:
            per_message_cost = float(resp.cost) / len(logs)
        except (TypeError, ValueError, ZeroDivisionError):
            per_message_cost = None

    for m in logs:
        m.status = 'sent'
        m.sent_at = now
        if batch_code:
            m.provider_ref = batch_code
        if per_message_cost is not None:
            m.provider_cost = per_message_cost
        # Keep only the first row's api_response to preserve the batch
        # summary without repeating it 200 times.
        m.api_response = None

    if logs:
        logs[0].api_response = (
            f'OK cost={resp.cost} code={batch_code}'
            if (batch_code or resp.cost is not None) else 'OK')

    db.session.flush()
    return len(logs), 0, 0


def _legacy_coerce(resp):
    """
    Wrap a legacy dict or list response so the loop can proceed.
    Only used when a caller passes the old shape.
    """
    if isinstance(resp, dict) and resp.get('error'):
        return EgoSMSResponse(ok=False, status='Error',
                              message=str(resp['error']))

    if isinstance(resp, dict):
        status = str(resp.get('status', '')).lower()
        if status == 'ok':
            return EgoSMSResponse(
                ok=True, status='OK',
                cost=resp.get('cost'),
                follow_up_code=(resp.get('messageFollowUpCode')
                                or resp.get('followUpCode')),
                raw=resp,
            )
        return EgoSMSResponse(
            ok=False, status='Failed',
            message=resp.get('message') or 'unknown error',
            raw=resp,
        )

    if isinstance(resp, list):
        all_ok = all(isinstance(r, dict) and r.get('status') == 'OK'
                     for r in resp)
        if all_ok:
            return EgoSMSResponse(ok=True, status='OK', raw=resp)
        return EgoSMSResponse(ok=False, status='Failed',
                              message='one or more messages failed',
                              raw=resp)

    return EgoSMSResponse(ok=False, status='InvalidResponse',
                          message=f'unexpected type: {type(resp).__name__}')