"""
Scheduled campaign sends.

A schedule is a list of exact datetimes. When the worker ticks and a
time is due, materialize_run creates a real Campaign with its own
wallet debit and its own recipient list resolved fresh from the
current contacts.

Datetimes are stored in local time (SCHEDULER_TZ_OFFSET_HOURS) as
ISO 8601 without seconds, e.g. "2026-10-15T09:00".
"""
import json
from datetime import datetime, timedelta

from app.extensions import db
from app.models import (CampaignSchedule, Campaign, Contact, MessageLog,
                        SendQueue, OptOut, Organization)
from app.services import wallet as wallet_svc
from app.services.entitlements import check_can_send, EntitlementError
from app.services.renderer import render, segments
from app.services.audit import log as audit
from app.permissions import department_filter


LOCAL_FMT = '%Y-%m-%dT%H:%M'


class ScheduleError(Exception):
    pass


# --------------------------------------------------------------------------
# Time helpers
# --------------------------------------------------------------------------

def _local_offset_hours():
    from flask import current_app
    return int(current_app.config.get('SCHEDULER_TZ_OFFSET_HOURS', 3))


def _local_now():
    return datetime.utcnow() + timedelta(hours=_local_offset_hours())


def _local_to_utc(dt_local):
    return dt_local - timedelta(hours=_local_offset_hours())


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def _parse_local(raw):
    """Return a naive local datetime from 'YYYY-MM-DDTHH:MM'."""
    if not raw:
        raise ScheduleError('A date and time is required.')
    raw = raw.strip()
    for fmt in (LOCAL_FMT, '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ScheduleError(
        f'Invalid date/time "{raw}". Use YYYY-MM-DDTHH:MM.')


def _validate_times(raw_list):
    """
    Return a sorted, deduplicated list of ISO local datetimes. All
    must be strictly in the future.
    """
    if not raw_list:
        raise ScheduleError('Add at least one date and time.')

    now = _local_now()
    seen = set()
    result = []

    for raw in raw_list:
        dt = _parse_local(raw)
        if dt <= now:
            raise ScheduleError(
                f'{dt.strftime("%d %b %Y %H:%M")} is in the past. '
                f'All times must be in the future.')
        iso = dt.strftime(LOCAL_FMT)
        if iso in seen:
            continue
        seen.add(iso)
        result.append(iso)

    if not result:
        raise ScheduleError('Add at least one valid date and time.')
    return sorted(result)


def _next_run_at(iso_times):
    """Earliest still-future ISO local time, converted to UTC, or None."""
    if not iso_times:
        return None
    now = _local_now()
    for iso in sorted(iso_times):
        dt_local = datetime.strptime(iso, LOCAL_FMT)
        if dt_local > now:
            return _local_to_utc(dt_local)
    return None


# --------------------------------------------------------------------------
# Create / lifecycle
# --------------------------------------------------------------------------

def create_schedule(org, *, name, body, times,
                    group_id=None, district_id=None,
                    template_id=None, created_by=None, user=None):
    name = (name or '').strip()
    body = (body or '').strip()
    if not name:
        raise ScheduleError('Campaign name is required.')
    if not body:
        raise ScheduleError('Message body is required.')

    scheduled_times = _validate_times(times)

    # #44: estimate recipients now and pre-reserve credits for all runs.
    # The school pays upfront; the reservation guarantees funds for every
    # fire, even if they spend the rest of their balance between now and then.
    estimate_contacts = _resolve_recipients(org.id, group_id, district_id)
    if not estimate_contacts:
        raise ScheduleError(
            'No eligible recipients for this group/district. '
            'Cannot create a schedule with zero recipients.')
    estimate_segments_per_run = sum(
        segments(render(org, body, c)) for c in estimate_contacts)
    total_reservation = estimate_segments_per_run * len(scheduled_times)

    try:
        check_can_send(org, total_reservation)
    except EntitlementError as e:
        raise ScheduleError(str(e))

    try:
        wallet_svc.debit(
            org.id, total_reservation,
            reason='schedule_reserve',
            note=(f'Schedule "{name}" - {len(estimate_contacts)} '
                  f'recipients x {len(scheduled_times)} run(s)'),
            actor_id=created_by,
        )
    except wallet_svc.InsufficientCredits as e:
        raise ScheduleError(str(e))

    schedule = CampaignSchedule(
        org_id=org.id,
        created_by=created_by,
        name=name,
        body=body,
        template_id=template_id,
        group_id=group_id,
        district_id=district_id,
        department=(user.department if user else None),
        sender_id=org.brand_name,
        scheduled_times=json.dumps(scheduled_times),
        status='active',
        credits_reserved=total_reservation,
    )
    schedule.next_run_at = _next_run_at(scheduled_times)
    db.session.add(schedule)
    db.session.commit()

    audit('schedule_create',
          f'id={schedule.id} count={len(scheduled_times)} '
          f'first={scheduled_times[0]}',
          org_id=org.id, actor_id=created_by)
    return schedule


def pause_schedule(schedule, *, reason=None, actor_id=None):
    if schedule.status != 'active':
        return False
    schedule.status = 'paused'
    schedule.pause_reason = (reason or '')[:255] or None
    db.session.commit()
    audit('schedule_pause',
          f'id={schedule.id} reason={reason or "-"}',
          org_id=schedule.org_id, actor_id=actor_id)
    return True


def resume_schedule(schedule, *, actor_id=None):
    if schedule.status != 'paused':
        return False
    schedule.status = 'active'
    schedule.pause_reason = None
    schedule.next_run_at = _next_run_at(schedule.times_list)
    if not schedule.next_run_at:
        # No future times left — nothing to resume.
        schedule.status = 'completed'
    db.session.commit()
    audit('schedule_resume',
          f'id={schedule.id} status={schedule.status}',
          org_id=schedule.org_id, actor_id=actor_id)
    return True


def cancel_schedule(schedule, *, actor_id=None):
    if schedule.status in ('cancelled', 'completed'):
        return False

    # #44: refund any remaining reservation. Legacy schedules
    # (credits_reserved IS NULL) never held a reservation; skip.
    if schedule.credits_reserved and schedule.credits_reserved > 0:
        wallet_svc.credit(
            schedule.org_id, schedule.credits_reserved,
            reason='schedule_cancel_refund',
            reference=f'schedule:{schedule.id}',
            note=f'Schedule cancelled with {schedule.credits_reserved} '
                 f'credits still reserved',
            actor_id=actor_id,
        )
        schedule.credits_reserved = 0

    schedule.status = 'cancelled'
    db.session.commit()
    audit('schedule_cancel', f'id={schedule.id}',
          org_id=schedule.org_id, actor_id=actor_id)
    return True


# --------------------------------------------------------------------------
# Worker-facing
# --------------------------------------------------------------------------

def claim_due_schedule():
    """
    Atomically claim one active schedule whose next_run_at has passed.

    Removes the earliest due time from the list, recomputes next_run_at,
    and marks the schedule completed when nothing is left.

    Returns (schedule_id, fired_iso_local) or None.
    """
    now_utc = datetime.utcnow()
    now_local = _local_now()

    # Fix #49: also select rows with next_run_at IS NULL, so an orphaned
    # active schedule (crashed between claim and materialize) can self-heal.
    _due_filter = db.or_(
        CampaignSchedule.next_run_at <= now_utc,
        CampaignSchedule.next_run_at.is_(None),
    )
    try:
        row = (CampaignSchedule.query
               .filter(CampaignSchedule.status == 'active')
               .filter(_due_filter)
               .order_by(CampaignSchedule.next_run_at.asc().nullsfirst())
               .with_for_update(skip_locked=True)
               .first())
    except Exception:
        db.session.rollback()
        row = (CampaignSchedule.query
               .filter(CampaignSchedule.status == 'active')
               .filter(_due_filter)
               .order_by(CampaignSchedule.next_run_at.asc().nullsfirst())
               .first())

    if not row:
        return None

    times = sorted(row.times_list)
    due = None
    remaining = []

    for iso in times:
        dt_local = datetime.strptime(iso, LOCAL_FMT)
        if due is None and dt_local <= now_local:
            due = iso
        else:
            remaining.append(iso)

    if due is None:
        # next_run_at was stale; recompute and move on.
        row.next_run_at = _next_run_at(times)
        if not times:  # no scheduled_times at all -> truly orphaned
            row.status = 'completed'
            # #44: refund any remaining reservation on orphan-complete.
            if row.credits_reserved and row.credits_reserved > 0:
                wallet_svc.credit(
                    row.org_id, row.credits_reserved,
                    reason='schedule_complete_refund',
                    reference=f'schedule:{row.id}',
                    note=f'Schedule completed with {row.credits_reserved} '
                         f'credits still reserved',
                    actor_id=None,
                )
                row.credits_reserved = 0
        db.session.commit()
        return None

    row.scheduled_times = json.dumps(remaining)
    row.last_run_at = now_utc
    row.next_run_at = _next_run_at(remaining)
    # Fix #49: do NOT set status='completed' here. If this is the last
    # run, materialize_run() will set it after firing. Setting it here
    # makes materialize_run's status check ('active' only) skip the run.
    db.session.commit()

    return row.id, due


def materialize_run(schedule_id, fired_iso=None):
    """
    Turn one schedule occurrence into a real Campaign.

    Debits the wallet, creates the Campaign, MessageLog rows, and
    SendQueue row in one transaction. On insufficient credits, pauses
    the schedule instead of failing the tick.
    """
    schedule = db.session.get(CampaignSchedule, schedule_id)
    if not schedule:
        return

    # If the schedule was cancelled or paused between claim and
    # materialize, drop the run silently.
    if schedule.status not in ('active',):
        return

    org = db.session.get(Organization, schedule.org_id)
    if not org or org.status != 'active':
        pause_schedule(schedule, reason='Organization suspended')
        return

    contacts = _resolve_recipients(org.id, schedule.group_id, schedule.district_id)
    if not contacts:
        schedule.runs_skipped = (schedule.runs_skipped or 0) + 1
        db.session.commit()
        return

    rendered = [(c, render(org, schedule.body, c)) for c in contacts]
    total_segments = sum(segments(m) for _, m in rendered)

    # #44: two paths. Legacy (credits_reserved IS NULL): debit at fire.
    # New (#44): credits already reserved at creation; check against
    # reservation, do not debit.
    is_legacy = schedule.credits_reserved is None

    if not is_legacy:
        # #44 path: check actual against remaining reservation.
        if total_segments > schedule.credits_reserved:
            # Contacts grew beyond what the school reserved. Skip this
            # run, refund the full remaining reservation, pause, warn.
            refund_amount = schedule.credits_reserved
            wallet_svc.credit(
                org.id, refund_amount,
                reason='schedule_overage_refund',
                reference=f'schedule:{schedule.id}',
                note=(f'Run skipped: {total_segments} recipients '
                      f'exceeds {refund_amount} reserved'),
                actor_id=schedule.created_by,
            )
            schedule.credits_reserved = 0
            schedule.runs_skipped = (schedule.runs_skipped or 0) + 1
            schedule.status = 'paused'
            schedule.pause_reason = (
                f'Recipients grew to {total_segments}, but only '
                f'{refund_amount} credits were reserved. '
                f'Re-create the schedule with current contacts.')[:255]
            db.session.commit()
            audit('schedule_overage',
                  f'schedule={schedule.id} actual={total_segments} '
                  f'reserved={refund_amount}',
                  org_id=org.id, actor_id=schedule.created_by)
            return
    else:
        # Legacy path: original behavior.
        try:
            check_can_send(org, total_segments)
        except EntitlementError as e:
            pause_schedule(schedule, reason=str(e)[:255])
            return

    campaign = Campaign(
        org_id=org.id,
        name=_run_name(schedule, fired_iso),
        body=schedule.body,
        template_id=schedule.template_id,
        sender_id=schedule.sender_id,
        group_filter=schedule.group.name if schedule.group else None,
        district_filter=schedule.district.name if schedule.district else None,
        status='queued',
        total=len(contacts),
        created_by=schedule.created_by,
        schedule_id=schedule.id,
        department=schedule.department,
    )
    db.session.add(campaign)
    db.session.flush()

    if is_legacy:
        # Legacy path: debit at fire time.
        try:
            wallet_svc.debit(
                org.id, total_segments, reason='sms_send',
                reference=f'campaign:{campaign.id}',
                note=f'Scheduled run (schedule {schedule.id})',
                actor_id=schedule.created_by,
            )
            campaign.credits_debited = total_segments
        except wallet_svc.InsufficientCredits as e:
            db.session.rollback()
            pause_schedule(schedule, reason=str(e)[:255])
            return
    else:
        # #44 path: credits already reserved. Just record the actual
        # on the campaign and decrement the reservation.
        campaign.credits_debited = total_segments
        schedule.credits_reserved = max(
            0, (schedule.credits_reserved or 0) - total_segments)

    for contact, msg in rendered:
        db.session.add(MessageLog(
            org_id=org.id, campaign_id=campaign.id,
            contact_id=contact.id, phone=contact.phone,
            body=msg, status='pending',
        ))

    db.session.add(SendQueue(
        campaign_id=campaign.id, org_id=org.id,
        status='pending', run_after=datetime.utcnow(),
    ))

    schedule.runs_completed = (schedule.runs_completed or 0) + 1
    schedule.total_sent = (schedule.total_sent or 0) + len(contacts)
    # Fix #49: mark completed only when no scheduled times remain.
    if not schedule.times_list:
        schedule.status = 'completed'
        # #44: refund any reservation left over (e.g. contacts shrank).
        if (not is_legacy) and schedule.credits_reserved \
                and schedule.credits_reserved > 0:
            leftover = schedule.credits_reserved
            wallet_svc.credit(
                org.id, leftover,
                reason='schedule_complete_refund',
                reference=f'schedule:{schedule.id}',
                note=(f'Schedule completed; {leftover} credits '
                      f'still reserved after final run'),
                actor_id=schedule.created_by,
            )
            schedule.credits_reserved = 0

    db.session.commit()

    audit('schedule_run',
          f'schedule={schedule.id} campaign={campaign.id} '
          f'recipients={len(contacts)} segments={total_segments}',
          org_id=org.id, actor_id=schedule.created_by)


def _resolve_recipients(org_id, group_id=None, district_id=None):
    """Current contacts matching the filters, minus opt-outs.

    Takes group_id/district_id directly (not a schedule object) so
    create_schedule can estimate recipients before the schedule exists.
    """
    q = Contact.query.filter_by(org_id=org_id, opted_out=False)
    if group_id:
        q = q.filter_by(group_id=group_id)
    if district_id:
        q = q.filter_by(district_id=district_id)
    contacts = q.all()
    blocked = {r[0] for r in db.session.query(OptOut.phone).all()}
    return [c for c in contacts if c.phone not in blocked]


def _run_name(schedule, fired_iso=None):
    """Human-readable name for the generated campaign."""
    if fired_iso:
        try:
            when = datetime.strptime(fired_iso, LOCAL_FMT)
            return f'{schedule.name} — {when.strftime("%d %b %H:%M")}'
        except ValueError:
            pass
    return f'{schedule.name} — {_local_now().strftime("%d %b %H:%M")}'

def list_for_org(org, user=None, limit=100):
    """List schedules for an org, filtered by the user's department.

    Mirrors app.services.campaigns.list_for_org.
    """
    query = CampaignSchedule.query.filter_by(org_id=org.id)
    if user is not None:
        query = department_filter(query, CampaignSchedule, user)
    return (query
            .order_by(CampaignSchedule.id.desc())
            .limit(limit).all())


def get_for_user(org, sid, user):
    """Fetch a single schedule by id, returning None if not visible.

    Returns None when:
      - no schedule with this id in this org
      - user.department is set and schedule.department is a different dept
    """
    schedule = CampaignSchedule.query.filter_by(
        org_id=org.id, id=sid).first()
    if schedule is None:
        return None
    if user is not None and getattr(user, 'department', None) is not None:
        if schedule.department not in (user.department, None):
            return None
    return schedule
