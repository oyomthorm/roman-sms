# Part 2 — Architecture

## 2.1 The layers, precisely

    ┌──────────────────────────────────────────────────────────────────┐
    │ Routes (18 HTML blueprints)   API v1 (12 JSON modules)           │
    │ Worker (schedule + send queue)  CLI (16 commands)                │
    └─────────────────────────┬────────────────────────────────────────┘
                              │
                              ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │ Services (31 modules) — every business rule                       │
    │ departments · wallet · campaigns · schedules · contacts · ...    │
    └─────────────────────────┬────────────────────────────────────────┘
                              │
                              ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │ Models (25 db.Model classes, 12 modules) — schema + relations    │
    └─────────────────────────┬────────────────────────────────────────┘
                              │
                              ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │ Postgres 16                                                       │
    └──────────────────────────────────────────────────────────────────┘

**Nothing enforces a rule twice.** If a rule lives in a service, the
route trusts the service. If a rule lives in a model (rare — only
convenience properties), both routes and worker see it identically.

## 2.2 Tenancy model

Three kinds of organization:

| Type | `is_master` | `is_system` | Purpose |
|---|---|---|---|
| Master | true | false | The operator (you). Sees every org. |
| System | false | true | Internal sender identity for pool campaigns. Never appears in the associate list. |
| Associate | false | false | Paying customers (schools and businesses). |

**Every tenant-scoped table carries an indexed `org_id`.** Reads go
through `org_scoped(Model)`:

    def org_scoped(model):
        if current_user.is_authenticated and current_user.role == 'master_admin':
            return model.query
        return model.query.filter_by(org_id=current_user.org_id)

Master bypasses the filter. Every other authenticated user is confined
to their own org.

**Department filtering layers on top of tenancy.** Once the org is
scoped, a second filter restricts by department (see §2.3).

## 2.3 Department isolation

Introduced in A1–A5. Every tenant-facing table that can be
department-scoped carries a nullable `department` column (indexed):
`user`, `contact_group`, `message_template`, `campaign`,
`campaign_schedule`.

The filter is one function:

    # app/permissions.py
    def department_filter(query, model, user):
        if user is None or user.department is None:
            return query
        return query.filter(
            or_(model.department == user.department,
                model.department.is_(None)))

**Semantics:**
- `user.department = None` (e.g. HT, school admin, master) → sees all
  records in their org.
- `user.department = 'bursar'` → sees only records where
  `department='bursar'` OR `department IS NULL` (shared).
- Every `create` service sets `record.department = current_user.department`.
  A bursar creates bursar-scoped records. An org admin creates shared
  records.

**No route accepts `department` from the form.** The value is always
the current user's own department. That is a security invariant.

Every read path applies the filter:
- `groups_svc.list_groups(org, user=)`
- `templates_svc.list_templates(org, user=)`
- `campaigns_svc.list_for_org(org, user=)`
- `schedules_svc.list_for_org(org, user=)`
- Plus per-model `get_for_user()` helpers that return `None` for
  cross-department IDs (which the route turns into a 404).

## 2.4 User lifecycle

`user.status` (String, default 'active') has three values:

| Status | Login | Create new sends | Scheduled fires |
|---|---|---|---|
| `active` | yes | yes | yes |
| `suspended` | yes (login allowed) | no (blocked at `/campaigns/new`) | yes (fired by worker regardless) |
| `terminated` | no (`is_active_flag=False`) | no | yes |

**Scheduled fires are not blocked by the creator's status.** The
school committed to the send at scheduling time; the reservation was
debit-ed. A bursar who leaves the school does not break their scheduled
campaigns.

`is_active_flag` (pre-existing Boolean) is kept in sync:
- suspend → `status='suspended'`, `is_active_flag=True`
- terminate → `status='terminated'`, `is_active_flag=False`
- reactivate → `status='active'`, `is_active_flag=True`

## 2.5 Request flow — send a campaign (send-now)

    POST /campaigns/new
      └─> campaigns.py::new()
            └─> svc.create_campaign(org, name=..., body=..., user=current_user)
                  ├─ resolve_recipients(org.id, group_id, district_id, ...)
                  │    └─ Contact.query.filter_by(org_id, opted_out=False)
                  │       minus platform OptOut list
                  ├─ render(org, body, contact) per recipient
                  ├─ check_can_send(org, total_segments)
                  │    ├─ org.status == 'active'?
                  │    ├─ active_subscription(org.id) exists?
                  │    └─ wallet.get_balance(org.id) >= total_segments?
                  ├─ Campaign(row) + db.session.flush() for id
                  ├─ wallet_svc.debit(org.id, total_segments,
                  │                    reason='sms_send',
                  │                    reference=f'campaign:{id}')
                  ├─ MessageLog(one per recipient, status='pending')
                  ├─ SendQueue(status='pending', run_after=now)
                  └─ db.session.commit()

    Worker tick:
      claim_jobs() → process_job(job_id)
        └─ dispatch calls Pahappa SendSms
              ├─ success: MessageLog.status='sent', provider_ref set
              ├─ failure: MessageLog.status='failed', wallet refunded
              └─ on last message: Campaign.status='complete',
                 email completion notification to org admins

    Pahappa webhook:
      POST /api/webhooks/transaction-status/<TOKEN>
        └─ MessageLog.status → 'delivered' or 'delivery_failed'

**Critical timing:** wallet is debit-ed in the *same transaction* as
Campaign insert. If the debit fails, no Campaign row exists. If the
debit succeeds and a later step fails, `db.session.rollback()` reverses
both. **The wallet and the campaign are always consistent.**

## 2.6 Request flow — schedule a campaign

    POST /campaigns/new with mode=schedule
      └─> schedules_svc.create_schedule(org, ..., user=current_user)
            ├─ validate_times(times)  # all future, deduped, sorted
            ├─ _resolve_recipients(org.id, group_id, district_id)
            ├─ segments_per_run = sum(segments(render(org, body, c)))
            ├─ total_reservation = segments_per_run × len(times)
            ├─ check_can_send(org, total_reservation)
            ├─ wallet_svc.debit(org.id, total_reservation,
            │                    reason='schedule_reserve',
            │                    reference=f'schedule:{id}')
            ├─ CampaignSchedule(row, credits_reserved=total_reservation)
            ├─ next_run_at = _next_run_at(times)  # earliest future UTC
            └─ db.session.commit()

    Worker scheduler pass, per tick:
      claim_due_schedule() loop:
        ├─ SELECT ... FOR UPDATE SKIP LOCKED
        │    WHERE status='active'
        │      AND (next_run_at <= now_utc OR next_run_at IS NULL)
        ├─ due = earliest times_list entry <= now_local
        ├─ remaining = times_list minus due
        ├─ schedule.scheduled_times = json.dumps(remaining)
        ├─ schedule.last_run_at = now
        ├─ schedule.next_run_at = _next_run_at(remaining)
        ├─ commit and return (schedule_id, due)
      materialize_run(schedule_id, fired_iso=due):
        ├─ if status != 'active': return (cancelled between claim and fire)
        ├─ if credits_reserved is None: legacy path (debit at fire)
        ├─ else: #44 path
        │    ├─ actual_segments = sum(segments(render(...)))
        │    ├─ if actual > credits_reserved:
        │    │    → skip run, refund full reservation, pause schedule
        │    └─ else: fire campaign, credits_reserved -= actual
        │         └─ if times_list == []: refund residual, mark completed

## 2.7 Request flow — billing

    POST /billing/plans/<pid>/buy
      └─> billing_svc.create_invoice(org, plan, user)
            ├─ Plan snapshot (price, credits, validity) into Invoice
            └─ Invoice(status='pending')

    Master marks paid at /master/invoices/<id>/mark-paid
      └─> billing_svc.mark_paid(invoice, actor)
            ├─ expire existing Subscription
            ├─ Subscription(row, from Invoice snapshot)
            ├─ wallet_svc.credit(org.id, invoice.credits,
            │                     source_org_id=master_org_id,
            │                     reason='plan_grant')
            └─ Invoice.status = 'paid'

**The invoice is the source of truth once issued.** PDF generation
reads the Invoice row alone — no live Plan or Organization lookup — so
what the customer paid for is what the PDF shows, forever.

## 2.8 Request flow — signup + approval

    POST /signup (unauthenticated)
      └─> signups_svc.submit_request(...)
            ├─ validate (slug format, email, brand length)
            ├─ check slug/email not in use by live org/user
            ├─ SignupRequest(row, status='pending')
            ├─ acknowledgement email to applicant
            └─ notification email to ALERT_EMAIL (master)

    Master approves at /master/signups/<id>/approve
      └─> signups_svc.approve(req, actor=master, starter_credits=N,
                              vertical='school'|'business'|None)
            ├─ re-validate slug/email still free
            ├─ Organization(row, vertical=...)
            ├─ User(row, role='associate_admin', random password hash)
            ├─ wallet_svc.transfer(master_id, org.id, starter_credits)
            ├─ SignupRequest.status='approved', reviewed_by/at
            └─ welcome email with password-set link (24h expiry)

## 2.9 Request flow — contact import

    POST /contacts/import (multipart)
      └─> contacts_svc.import_csv(org, file_stream, ...)
            ├─ ContactImport(row)
            ├─ for each row in CSV:
            │    ├─ normalize_ug(phone)
            │    ├─ if invalid → skip, ContactImportIssue(reason)
            │    ├─ if in OptOut → skip, ContactImportIssue(reason)
            │    ├─ if duplicate in file → skip, ContactImportIssue(reason)
            │    ├─ if duplicate in DB → skip (or update), issue row
            │    └─ else: Contact(row)
            ├─ ContactImport.status='complete'
            └─ Redirect to /contacts/imports/<id>
                 (counts, filter tabs, downloadable error CSV)

## 2.10 Pool sharing (master-initiated cross-org sends)

Pool = cross-org contact sharing with per-associate consent.

    Associate Settings → Enable pool sharing
      └─> pool_svc.grant_permission(org, agreement_text, actor)
            ├─ PoolPermission(row, agreement_text=verbatim)
            └─ copy contacts into PoolContact rows
                 (snapshot group_name, district_id, source_org_id)

    Master /master/pool
      └─> pool_svc.list_pool_groups() + filter by district/group/org
            └─> POST /master/pool/send
                  ├─ resolve from PoolContact
                  ├─ send from the system sender org (is_system=True)
                  └─ wallet_svc.debit(system_org.id, ...)

    Revoke:
      └─> pool_svc.revoke_permission(org)
            └─ delete PoolContact rows for that org

**Opt-out propagation:** every opt-out entry point
(public landing, manual contact opt-out, import with opted_out column)
calls `propagate_opt_out(phone)` which touches OptOut AND
PoolContact rows for that phone.

## 2.11 Wallet invariants

`wallet_transaction` is append-only. `wallet.get_balance(org_id)` is
`SUM(delta)`, cached into `balance_after` on each row.

**Invariants:**
- `SUM(delta) == last.balance_after` (verified by `scripts/reconcile.py`)
- Every `credit()` without `source_org_id` must use a reason from
  `EXTERNAL_CREDIT_REASONS` (`master_opening_balance`, `master_topup`,
  `pahappa_sync`, `refund`, `adjustment`, `schedule_cancel_refund`,
  `schedule_partial_refund`, `schedule_complete_refund`,
  `schedule_overage_refund`).
- Every internal movement (transfer, refund after failure) must have
  `source_org_id` set or be a legitimate external credit.
- **Postgres is required in production.** Wallet writes take `SELECT
  ... FOR UPDATE` on the org row. SQLite would not serialize.

## 2.12 Worker

`worker.py` is a single Python process. Two passes per tick:

1. **Scheduler pass:** `claim_due_schedule()` in a loop until no due
   schedules remain. Each claimed schedule is materialized.
2. **Send queue drain:** `dispatch.claim_jobs(limit=5)` then
   `dispatch.process_job(jid)` per job. Batch rate-limited per org.

**Rate limits** (per org, from `Plan.max_per_minute` and
`Plan.max_per_day`): counted from `MessageLog.status='sent'`. Enforced
inside `dispatch.process_job` — a batch never exceeds the minute
budget; a daily cap requeues for one hour later.

**No Celery, no Redis.** Database-backed queue with
`SELECT ... FOR UPDATE SKIP LOCKED`. See ADR-003.

## 2.13 Notifications

Computed on every render from live conditions (low balance, plan
expiring, no contacts, etc.). **No stored inbox.** Per-user dismissals
(`NotificationDismissal`) hide specific conditions; the notification
disappears on its own when the condition clears. See ADR-008.

## 2.14 Chat

DM (master ↔ one associate) + broadcast (all). 3-second polling while
the chat page is open. Read state per user per channel. No websockets.

## 2.15 Dashboard

`routes/dashboard.py` computes:
- `sent_30d` — messages with `status IN ('sent','delivered','delivery_failed')`
- `delivered_30d`, `delivery_failed_30d` — subsets confirmed by webhook
- `failed_30d`, `pending_30d` — independent counters
- `trend` — 30-slot list including zero-days
- `avg_daily_spend`, `days_remaining` — derived from wallet debits
  with `reason='sms_send'`

Charts are inline SVG. No JS chart library. See ADR-016.

## 2.16 Logging

`app/logging_config.py` — text (dev) or JSON (prod). Per-request IDs
via `X-Request-ID`. Nginx proxies the header through to Flask. Log lines
from the worker carry no request ID (no request context).

## 2.17 Mobile API

`/api/v1/*` is the JSON surface for the Flutter client. It is a third
consumer of the same services as the web app. **No business logic lives
in `app/api/v1/`.** Handlers do argument adaptation, serialization, and
error mapping only.

**Auth:** Bearer tokens from `POST /api/v1/auth/login`. Tokens are
opaque `rsms_<random>` strings stored hashed in `api_tokens`. Expiry
enforced by the token table, not a claim. No cookies, no CSRF.

**CSRF exemption:** the entire `/api/v1/*` tree is CSRF-exempt, applied
per-child-blueprint in `app/api/v1/__init__.py`. Flask-WTF does not
cascade exemptions from parent to child. Every new child blueprint must
be added to `_CHILDREN` for exemption.

**Serialization invariants:**
- `org_id` always comes from `current_user.org_id`, never from the
  request.
- Every GET returns `{"items": [...]}` for lists or the resource
  directly for single-item reads.
- Decimal fields (`price_ugx`, `rate_ugx`, `value_ugx`) serialize as
  **strings** to preserve precision. Clients parse with `num.parse()`.
- Campaign creation requires an `Idempotency-Key` header.

See Part 6 for the full mobile API reference.

---

*Part 2 of 10. See `03-features.md` next.*