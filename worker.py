"""
Roman SMS — background worker.

Two responsibilities, run in a single loop on every tick:

  1. Scheduler pass
     Claim due campaign schedules and materialize each one into a real
     Campaign. Runs first so a due slot is never delayed by a busy
     send queue.

  2. Send queue drain
     Claim pending SendQueue rows and process them via
     services.dispatch.process_job(). Batches are rate-limited per org.

Run as a separate process:

    python worker.py

Logs go to stdout. Under systemd, capture them with
journalctl -u roman-worker.
"""
import logging
import time
import traceback

from app import create_app
from app.extensions import db
from app.services import dispatch
from app.services import schedules as schedule_svc


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [worker] %(levelname)s %(message)s',
)
log = logging.getLogger('roman.worker')

# Surface dispatch's own logs to the console.
logging.getLogger('roman.dispatch').setLevel(logging.INFO)


# --------------------------------------------------------------------------
# Scheduler pass
# --------------------------------------------------------------------------

def run_scheduler_pass():
    """
    Materialize every schedule whose next send time is due.

    claim_due_schedule() returns (schedule_id, fired_iso) — the id of
    the schedule that was claimed plus the local ISO datetime that
    triggered the run. Each call removes one due time from the
    schedule's list, so the loop drains a backlog in a single tick
    rather than one per poll interval.

    Returns the number of schedules materialized.
    """
    count = 0
    while True:
        try:
            claim = schedule_svc.claim_due_schedule()
        except Exception:
            log.exception('claim_due_schedule failed')
            db.session.rollback()
            break

        if not claim:
            break

        schedule_id, fired_iso = claim

        try:
            schedule_svc.materialize_run(schedule_id, fired_iso=fired_iso)
            count += 1
        except Exception:
            log.exception('materialize_run failed for schedule %s '
                          '(fired %s)', schedule_id, fired_iso)
            db.session.rollback()
            # The claim already removed this time from the list, so a
            # failed materialization skips this slot rather than
            # looping forever. Move on.

    if count:
        log.info('Scheduler: materialized %s schedule(s).', count)
    return count


# --------------------------------------------------------------------------
# Send queue pass
# --------------------------------------------------------------------------

def run_send_pass():
    """
    Claim up to 5 pending jobs and process each one.

    Returns the number of jobs claimed.
    """
    ids = dispatch.claim_jobs(limit=5)
    if not ids:
        return 0

    log.info('Claimed %s job(s): %s', len(ids), ids)
    for jid in ids:
        try:
            dispatch.process_job(jid)
        except Exception:
            log.exception('job %s failed', jid)
            db.session.rollback()
    return len(ids)


# --------------------------------------------------------------------------
# Main loop
# --------------------------------------------------------------------------

def main():
    app = create_app()
    log.info('Roman SMS worker started.')
    log.info('Poll interval: %ss  Batch size: %s  Mode: %s',
             app.config['WORKER_POLL_SECONDS'],
             app.config['WORKER_BATCH_SIZE'],
             app.config.get('EGOSMS_API_MODE'))

    idle_ticks = 0

    with app.app_context():
        while True:
            try:
                # ---- 1. Scheduler ----
                try:
                    run_scheduler_pass()
                except Exception:
                    log.exception('scheduler pass error')
                    db.session.rollback()

                # ---- 2. Send queue ----
                try:
                    requeued = dispatch.requeue_stuck()
                    if requeued:
                        log.warning('Requeued %s stuck job(s).', requeued)
                except Exception:
                    log.exception('requeue_stuck failed')
                    db.session.rollback()

                try:
                    claimed = run_send_pass()
                except Exception:
                    log.exception('send pass error')
                    db.session.rollback()
                    claimed = 0

                # ---- Idle handling ----
                if claimed == 0:
                    idle_ticks += 1
                    if idle_ticks % 10 == 1:
                        log.info('Idle. Queue empty. (checked %s times)',
                                 idle_ticks)
                    time.sleep(app.config['WORKER_POLL_SECONDS'])
                else:
                    idle_ticks = 0

            except KeyboardInterrupt:
                log.info('Worker stopping.')
                break

            except Exception:
                log.error('Worker loop error:\n%s', traceback.format_exc())
                # Roll back any half-open transaction so the next tick
                # starts clean.
                try:
                    db.session.rollback()
                except Exception:
                    pass
                time.sleep(10)


if __name__ == '__main__':
    main()