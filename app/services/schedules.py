"""
Recurring campaign schedules.

A schedule is a rule. Each time it fires, we materialize one real
Campaign with its own wallet debit, recipient list, and message logs.
"""
import json
from datetime import datetime, timedelta, time as dtime

from app.extensions import db
from app.models import (CampaignSchedule, Campaign, Contact, MessageLog,
                        SendQueue, OptOut, Organization)
from app.services import wallet as wallet_svc
from app.services.entitlements import check_can_send, EntitlementError
from app.services.renderer import render, segments
from app.services.audit import log as audit


VALID_DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
WEEKDAY_INDEX = {d: i for i, d in enumerate(VALID_DAYS)}  # mon=0


class ScheduleError(Exception):
    pass


# --------------------------------------------------------------------------
# Time helpers
# --------------------------------------------------------------------------

def _local_offset_hours():
    from flask import current_app
    return int(current_app.config.get('SCHEDULER_TZ_OFFSET_HOURS', 3))


def _local_now():
    """Current time in the schedule's local timezone."""
    return datetime.utcnow() + timedelta(hours=_local_offset_hours())


def _local_to_utc(dt_local):
    """Convert a local-time datetime to UTC for storage."""
    return dt_local - timedelta(hours=_local_offset_hours())


# --------------------------------------------------------------------------
# Recurrence computation
# --------------------------------------------------------------------------

def compute_next_run(schedule, *, after_local=None):
    """
    Return the next UTC datetime this schedule should fire, or None if
    there is no future occurrence (ended or no days/times).

    Walks forward up to 8 days from `after_local`. If nothing matches
    inside that window, returns None.
    """
    days = schedule.days_list
    times = schedule.times_list
    if not days or not times:
        return None

    if after_local is None:
        after_local = _local_now()

    parsed_times = sorted(
        (dtime(int(t.split(':')[0]), int(t.split(':')[1])) for t in times),
        key=lambda t: (t.hour, t.minute),
    )

    enabled = {WEEKDAY_INDEX[d] for d in days if d in WEEKDAY_INDEX}

    for day_offset in range(0, 9):
        candidate_date = after_local.date() + timedelta(days=day_offset)

        if schedule.starts_on and candidate_date < schedule.starts_on:
            continue
        if schedule.ends_on and candidate_date > schedule.ends_on:
            return None

        if candidate_date.weekday() not in enabled:
            continue

        for t in parsed_times:
            candidate_local = datetime.combine(candidate_date, t)
            if candidate_local > after_local:
                return _local_to_utc(candidate_local)

    return None


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def _validate_days(days):
    if not days:
        raise ScheduleError('Pick at least one day of the week.')
    clean = sorted({d.strip().lower() for d in days if d and d.strip()})
    bad = [d for d in clean if d not in VALID_DAYS]
    if bad:
        raise ScheduleError(f'Invalid day code: {", ".join(bad)}.')
    return ','.join(clean)


def _validate_times(times):
    if not times:
        raise ScheduleError('Add at least one time of day.')
    clean = []
    seen = set()
    for t in times:
        t = (t or '').strip()
        if not t:
            continue
        parts = t.split(':')
        if len(parts) != 2:
            raise ScheduleError(f'Invalid time: {t}. Use HH:MM.')
        try:
            h, m = int(parts[0]), int(parts[1])
        except ValueError:
            raise ScheduleError(f'Invalid time: {t}. Use HH:MM.')
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ScheduleError(f'Invalid time: {t}.')
        normalized = f'{h:02d}:{m:02d}'
        if normalized not in seen:
            clean.append(normalized)
            seen.add(normalized)
    if not clean:
        raise ScheduleError('Add at least one valid time of day.')
    return sorted(clean)


# --------------------------------------------------------------------------
# Create / lifecycle
# --------------------------------------------------------------------------

def create_schedule(org, *, name, body, days, times,
                    starts_on, ends_on=None,
                    group_id=None, district_id=None,
                    template_id=None, created_by=None):
    name = (name or '').strip()
    body = (body or '').strip()
    if not name:
        raise ScheduleError('Campaign name is required.')
    if not body:
        raise ScheduleError('Message body is required.')

    days_str = _validate_days(days)
    times_list = _validate_times(times)

    if isinstance(starts_on, str):
        try:
            starts_on = datetime.strptime(starts_on, '%Y-%m-%d').date()
        except ValueError:
            raise ScheduleError('Invalid start date.')

    if ends_on:
        if isinstance(ends_on, str):
            try:
                ends_on = datetime.strptime(ends_on, '%Y-%m-%d').date()
            except ValueError:
                raise ScheduleError('Invalid end date.')
        if ends_on < starts_on:
            raise ScheduleError('End date must be on or after start date.')

    schedule = CampaignSchedule(
        org_id=org.id,
        created_by=created_by,
        name=name, body=body,
        template_id=template_id,
        group_id=group_id,
        district_id=district_id,
        sender_id=org.brand_name,
        days_of_week=days_str,
        times_of_day=json.dumps(times_list),
        starts_on=starts_on,
        ends_on=ends_on,
        status='active',
    )
    schedule.next_run_at = compute_next_run(schedule)
    db.session.add(schedule)
    db.session.commit()

    audit('schedule_create',
          f'id={schedule.id} days={days_str} times={json.dumps(times_list)}',
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
    schedule.next_run_at = compute_next_run(schedule)
    db.session.commit()
    audit('schedule_resume', f'id={schedule.id}',
          org_id=schedule.org_id, actor_id=actor_id)
    return True


def cancel_schedule(schedule, *, actor_id=None):
    if schedule.status in ('cancelled', 'completed'):
        return False
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

    Advances next_run_at immediately so a crash during materialization
    skips this tick rather than firing twice.

    Returns the schedule id or None.
    """
    now = datetime.utcnow()

    try:
        row = (CampaignSchedule.query
               .filter(CampaignSchedule.status == 'active')
               .filter(CampaignSchedule.next_run_at <= now)
               .order_by(CampaignSchedule.next_run_at.asc())
               .with_for_update(skip_locked=True)
               .first())
    except Exception:
        db.session.rollback()
        row = (CampaignSchedule.query
               .filter(CampaignSchedule.status == 'active')
               .filter(CampaignSchedule.next_run_at <= now)
               .order_by(CampaignSchedule.next_run_at.asc())
               .first())

    if not row:
        return None

    row.last_run_at = now
    row.next_run_at = compute_next_run(row, after_local=_local_now())

    # Mark completed if the window has ended and there is no next slot
    if row.next_run_at is None and row.status == 'active':
        row.status = 'completed'

    db.session.commit()
    return row.id


def materialize_run(schedule_id):
    """
    Turn one schedule occurrence into a real Campaign.

    Debits the wallet, creates the Campaign, MessageLog rows, and
    SendQueue row in one transaction. On insufficient credits, pauses
    the schedule instead of failing the tick.
    """
    schedule = db.session.get(CampaignSchedule, schedule_id)
    if not schedule or schedule.status != 'active':
        return

    org = db.session.get(Organization, schedule.org_id)
    if not org or org.status != 'active':
        pause_schedule(schedule, reason='Organization suspended')
        return

    contacts = _resolve_recipients(org.id, schedule)
    if not contacts:
        schedule.runs_skipped = (schedule.runs_skipped or 0) + 1
        db.session.commit()
        return

    rendered = [(c, render(org, schedule.body, c)) for c in contacts]
    total_segments = sum(segments(m) for _, m in rendered)

    try:
        check_can_send(org, total_segments)
    except EntitlementError as e:
        pause_schedule(schedule, reason=str(e)[:255])
        return

    campaign = Campaign(
        org_id=org.id,
        name=_run_name(schedule),
        body=schedule.body,
        template_id=schedule.template_id,
        sender_id=schedule.sender_id,
        group_filter=schedule.group.name if schedule.group else None,
        district_filter=schedule.district.name if schedule.district else None,
        status='queued',
        total=len(contacts),
        created_by=schedule.created_by,
        schedule_id=schedule.id,
    )
    db.session.add(campaign)
    db.session.flush()

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

    db.session.commit()

    audit('schedule_run',
          f'schedule={schedule.id} campaign={campaign.id} '
          f'recipients={len(contacts)} segments={total_segments}',
          org_id=org.id, actor_id=schedule.created_by)


def _resolve_recipients(org_id, schedule):
    """Current contacts matching the schedule's filters, minus opt-outs."""
    q = Contact.query.filter_by(org_id=org_id, opted_out=False)
    if schedule.group_id:
        q = q.filter_by(group_id=schedule.group_id)
    if schedule.district_id:
        q = q.filter_by(district_id=schedule.district_id)
    contacts = q.all()
    blocked = {r[0] for r in db.session.query(OptOut.phone).all()}
    return [c for c in contacts if c.phone not in blocked]


def _run_name(schedule):
    """Human-readable name for the generated campaign."""
    local = _local_now()
    return f'{schedule.name} — {local.strftime("%d %b %H:%M")}'