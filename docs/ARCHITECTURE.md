# Architecture

## Layers
Routes ─┐
Worker ─┼─▶ Services ─▶ Models ─▶ Postgres
CLI ─┘ │
└─▶ Pahappa Comms API ─▶ Networks
▲
│
Webhook receiver ◀── Delivery reports


Routes are HTTP glue. Services contain every business rule. The worker
and the CLI call the same services. Nothing enforces a rule twice.

## Tenancy

Three kinds of organization, distinguished by two flags:

| Type | `is_master` | `is_system` | What it is |
|---|---|---|---|
| Master | True | False | The operator (you) |
| System | False | True | Internal sending identity |
| Associate | False | False | Paying clients |

Every tenant table carries an indexed `org_id`. Reads go through
`org_scoped(Model)`. The master bypasses the filter. The system org is
not visible to associates and never appears in the associate list.

## Request flows

### Sending a campaign

**Two ways to specify recipients:**

- **From contacts** — the associate picks a group, a district, or
  both. Recipients are resolved at submit time from `Contact` rows
  scoped to the org, minus opted-out.
- **Paste numbers** — the associate pastes a list of phone numbers
  into a textarea. The route parses each with
  `services.phones.normalize_ug`, skips duplicates, skips numbers on
  the platform-wide `OptOut` list, and (optionally) sends the campaign
  without creating `Contact` rows for those numbers. Capped at 500.

Both paths converge in `services.campaigns.create_campaign`. When the
source is a paste list, the route passes the resolved numbers as
synthetic `Contact`-shaped objects so the service does not need a
second code path.

**Live cost preview on the form:**

The new-campaign form has a small script that mirrors the segment
arithmetic from `services.renderer.segments`. As the associate types,
it computes `len(brand_prefix + body)` and shows the segment count and
shilling cost using the org's current rate (`wallet_rate` from the
context processor). The counter counts the **full delivered message**,
including the prefix, because that is what Pahappa bills for.

**Pipeline (unchanged):**

1. Route calls `services.campaigns.create_campaign(org, ...)`.
2. Service:
   - resolves recipients (org-scoped, not opted out)
   - renders each message (brand prefix + substituted body; see ADR-017)
   - checks entitlements (status, plan, credits)
   - inserts Campaign, flushes for its id
   - **debits the wallet before dispatch, in the same transaction**
   - inserts one MessageLog per recipient
   - inserts one SendQueue row
   - commits
3. Worker: `claim_jobs()` → `process_job(job_id)`.
4. Dispatch calls Pahappa, marks each row sent or failed, refunds the
   wallet for failures, and stores `provider_ref` + `provider_cost`.
5. Pahappa POSTs delivery reports to the webhook, which flips matching
   `MessageLog.status` to `delivered` or `delivery_failed`.

### Scheduling a recurring campaign

1. Associate chooses "Schedule" on the new-campaign form. The days
   checkboxes, times-of-day rows, and active window are always visible
   but dimmed when "Send now" is selected.
2. Route calls `services.schedules.create_schedule(...)`.
3. Service validates the days (3-letter codes) and times (`HH:MM`),
   normalises start and end dates, and stores the rule in
   `CampaignSchedule` with `next_run_at` computed from the current
   local time plus the configured `SCHEDULER_TZ_OFFSET_HOURS`.
4. On each worker tick, `run_scheduler_pass()` calls
   `claim_due_schedule()` in a loop until no due schedules remain.
5. `materialize_run(schedule_id)`:
   - re-checks org status (suspended → pause schedule)
   - resolves recipients fresh (new contacts included, opt-outs excluded)
   - checks entitlements
   - creates a real `Campaign` linked back via `Campaign.schedule_id`
   - debits the wallet per run
   - inserts `MessageLog` rows and a `SendQueue` row
   - updates schedule counters
   - commits
6. On insufficient credits, the schedule pauses itself with a clear
   reason. The associate sees the reason on the schedule detail page
   and a link to top up.

### Buying credits

1. Associate clicks Buy on the plans page.
2. `services.billing.create_invoice` creates an Invoice with the plan's
   price, credits, and validity **snapshotted**.
3. Associate pays offline; master marks the invoice paid.
4. `services.billing.mark_paid` in one transaction expires any existing
   subscription, creates a new one from the snapshot, credits the
   wallet, and marks the invoice paid.
5. Either party can download the invoice as a PDF from the invoice
   detail page. `services.invoice_pdf` renders it from the Invoice row
   alone — no live lookups against Plan or Organization — because the
   invoice is the source of truth once issued.

### Signup

1. Applicant fills `/signup`.
2. `services.signups.submit_request` creates a `SignupRequest` row.
   Nothing else is created.
3. Acknowledgement email to the applicant, notification to
   `ALERT_EMAIL`, in-app notification for the master.
4. Master approves at `/master/signups/<id>`.
5. `services.signups.approve` creates the Organization, admin User,
   and starter credit grant in one transaction, then sends a welcome
   email with a password-setup link.

### Contact import

1. Associate uploads a CSV at `/contacts/import`.
2. Client-side preview shows every row with its normalized phone and
   status before upload.
3. On submit, `services.contacts.import_csv` creates a
   `ContactImport` job, normalizes each phone, categorises every
   skipped row (invalid, opted-out, duplicate in file, duplicate in
   DB), and commits.
4. Associate lands on `/contacts/imports/<id>` with counts, filter
   tabs, and a downloadable error CSV.

### Pool sharing

1. Associate grants permission on Settings. Full agreement text is
   snapshot into `PoolPermission.agreement_text`.
2. Contacts copy into `PoolContact`, one row per `(source_org, phone)`,
   with `group_name` and `district_id` snapshotted.
3. `propagate_opt_out` fires from every opt-out entry point.
4. Master sends pool campaigns from the system org, with optional
   district and group filters.
5. Revocation deletes the org's `PoolContact` rows.

## Wallet

Append-only. `WalletTransaction` rows are insert-only. Balance is
`SUM(delta)`. Each row caches `balance_after`.

Invariant: `SUM(delta) == last.balance_after`. The nightly
`scripts/reconcile.py` asserts this and alerts on drift.

Writes take a `SELECT ... FOR UPDATE` lock on the org row before
reading the balance. **Postgres is required in production.**

## Display layer — credits vs shillings

Internal accounting is in integer credits. Every balance shown to an
associate is in UGX, using `services.entitlements.current_rate_ugx`
(the active plan's derived rate, or a fallback). The context processor
injects `wallet_balance`, `wallet_rate`, and `wallet_value_ugx` into
every authenticated template.

## Master sender identity

One master sender ID for the whole platform, registered with Pahappa.
Associate branding is a message body prefix applied by
`services.renderer.with_prefix`. See ADR-002.

## Worker

Database-backed queue. `send_queue` table, `SELECT ... FOR UPDATE SKIP
LOCKED` claim, plain Python process. The worker runs two passes per
tick: scheduler first, then send queue drain. Two systemd units
(web + worker). No Celery, no Redis.

## Rate limits

Per org, driven by `Plan.max_per_minute` and `Plan.max_per_day`.
Counted from `MessageLog.status='sent'`. Enforced inside
`dispatch.process_job`: batches never exceed the minute budget, and a
daily cap requeues the job for one hour later.

## Notifications

Computed on every render from live conditions. No stored inbox.
Per-user dismissals (`NotificationDismissal`) hide specific conditions;
the notification disappears on its own when the condition clears.

## Campaign completion emails

When `dispatch.process_job` flips a Campaign to `complete`, it calls
`services.campaign_notifications.send_completion_email(campaign_id)`.
The service emails the campaign creator plus every active
`associate_admin` in the org, deduplicated. Gated by
`EMAIL_ON_CAMPAIGN_COMPLETE` config flag.

Renders the body with Jinja2's `Template` directly, not Flask's
`render_template_string` — the latter runs Flask's context processors,
which expect a request context that the worker does not have.

The call is wrapped in try/except so a mail failure never breaks the
dispatch loop.

## Dashboard

`routes/dashboard.py` computes:

- `sent_30d` — messages that reached the network. Population is
  `status IN ('sent', 'delivered', 'delivery_failed')`.
- `delivered_30d`, `delivery_failed_30d` — subsets of `sent_30d`
  confirmed by the webhook.
- `failed_30d`, `pending_30d` — independent counters, not subsets of
  `sent_30d`.
- `trend` — 30-slot list, one entry per day including zero-days.
- `avg_daily_spend` and `days_remaining` — derived from wallet debits
  with `reason='sms_send'` over the last 30 days.

All charts are inline SVG rendered in the template. No JS library.
See ADR-016.

## Chat

DM (master ↔ one associate) and broadcast. 3-second polling while the
chat page is open. Read state per user per channel. No websockets.

## Logging

Text (dev) or JSON (prod) via `app/logging_config.py`. Per-request IDs
attached via `X-Request-ID`.


---

## Mobile API

`/api/v1/*` is the JSON surface for the Flutter mobile client. It is a
third consumer of the same services that back the web app — no business
logic lives in `app/api/v1/`. Every `/api/v1/*` handler delegates to a
`services.*` function; handlers do serialization, argument shape
adaptation, and error mapping only.

### Authentication

Bearer tokens issued by `POST /api/v1/auth/login`. Tokens are opaque
`rsms_<random>` strings stored hashed in `ApiToken`. Expiry is enforced
by the token table, not by a claim in the token. No cookies, no CSRF.

The Bearer token is loaded per-request by `install_api_auth` via
Flask-Login's `login_manager.request_loader`. Existing decorators
(`@login_required`, `@org_admin_required`) work unchanged for API
requests.

### CSRF exemption

The entire `/api/v1/*` blueprint tree is CSRF-exempt, applied per-child
in `app/api/v1/__init__.py` via `csrf.exempt(child_bp)` for each child
before registration. **Flask-WTF does not cascade exemptions from a
parent blueprint to its children**, so exempting `api_v1_bp` alone is
insufficient. Every new child blueprint added to `api_v1_bp` must be
added to the `_CHILDREN` tuple for exemption.

### Invariants

- **`org_id` comes from `current_user.org_id`, never from the request.**
  Same rule as PERMISSIONS.md; the mobile API inherits it.
- Every `/api/v1/*` GET returns `{"items": [...]}` for lists or the
  resource directly for single-item reads.
- Decimal fields (`price_ugx`, `rate_ugx`, `value_ugx`) serialize as
  **strings**, not numbers, to preserve precision. Flutter clients must
  parse with `num.parse(...)` or `double.parse(...)`, never
  `int.parse(...)`.
- Campaign creation requires an `Idempotency-Key` header.
- `/api/v1/auth/signup` is anonymous, 5/hour/IP rate-limited, returns
  201 but does NOT issue a token.

### Testing

The mobile API has no automated test coverage as of 0.12.0. The
verification pattern used during the 0.11.0–0.12.0 audit was a
`test_client()` loop hitting every GET endpoint with a real login token.
This should be promoted to `tests/integration/test_mobile_api.py`
before the next round of features lands on the API. See ADR-019.

### Deferred

See `CHANGELOG.md` 0.12.0 "Discovered, not fixed" for the list of
endpoints and features deferred to 0.13.0+. Full parity is planned
across 15 sequential rounds (ADR-021).

## Model additions in the department/lifecycle arc (2026-11-10 → 2026-11-13)

Five tables carry a nullable, indexed `department` column: `user`,
`contact_group`, `message_template`, `campaign`, `campaign_schedule`.
`NULL` means "shared" (visible to all departments).

`user` additionally has:
- `status` — `'active' | 'suspended' | 'terminated'` (NOT NULL, default `active`)
- `status_changed_at` — when the last status transition happened

`organization` has:
- `vertical` — `'school' | 'business' | NULL` (NULL = unclassified)

`campaign_schedule` has:
- `credits_reserved` — integer, the credits held against future runs.
  `NULL` means "legacy schedule" (created before the reservation model
  existed); those debit at fire time like the pre-#44 behavior.

## Department isolation

Every tenant read that could leak across departments goes through one
helper: `app.permissions.department_filter(query, model, user)`.

- `user is None` or `user.department is None` → filter is a no-op (HT,
  school admin, master all see everything in their org).
- Otherwise the filter is `model.department == user.department OR
  model.department IS NULL` — the user sees their department's records
  plus shared records, never another department's.

Write path: `current_user.department` is passed into every create
service (`svc.create(..., department=current_user.department)`). A user
with `department='bursar'` creates bursar-scoped records. A user with
`department=None` creates shared (`NULL`) records. **No route accepts
`department` from the form** — the department is always the creator's.
That is a security invariant, not an accident.

A5 (school-admin user CRUD) is the only way to set a user's department,
and master can also set it via `/master/orgs/<id>/edit` after signup
approval. See `DEPARTMENTS.md` for the Q1/Q2/Q3 answers (who manages
users, who pays, when credits are debited).

## User lifecycle

`user.status` has three states with distinct enforcement:

| State | Login | Send (create campaign / schedule) | Reversible |
|---|---|---|---|
| `active` | ✅ | ✅ | n/a |
| `suspended` | ✅ | ❌ (blocked at `routes/campaigns.py::new`) | ✅ via reactivate |
| `terminated` | ❌ (blocks at `routes/auth.py::login` via `is_active_flag=False`) | ❌ | ✅ via reactivate |

`is_active_flag` (the pre-existing Boolean) is kept in sync:
- suspend → `status='suspended'`, `is_active_flag=True`
- terminate → `status='terminated'`, `is_active_flag=False`
- reactivate → `status='active'`, `is_active_flag=True`

**Scheduled fires are not blocked by the creator's status.** A schedule
created by a bursar who later leaves the school still fires; the school
committed to the send, and #44 reserved the credits for it. Only
*initiating new sends* is blocked.

Guards in `orgs_svc.suspend_user` / `terminate_user`:
- Cannot suspend/terminate yourself
- Cannot suspend/terminate the last active `associate_admin` in the org

## Schedule reservation model (#44 + #16)

**At create** (`schedules.create_schedule`):
- Estimate recipient count from current contacts
- Compute `segments_per_run = sum(segments(render(org, body, c)))`
- Compute `total_reservation = segments_per_run × len(times)`
- `check_can_send(org, total_reservation)` then `wallet_svc.debit(...)`
  with `reason='schedule_reserve'`, `reference='schedule:<id>'`
- Store `credits_reserved = total_reservation` on the row

**At fire** (`schedules.materialize_run`):
- If `credits_reserved is None` → legacy path: `check_can_send` + debit
  at fire (unchanged pre-#44 behavior)
- Else → #44 path:
  - If `actual_segments > credits_reserved` → **overage**: skip the run,
    refund the full remaining reservation (`schedule_overage_refund`),
    pause the schedule with a clear reason
  - Else → fire, `credits_reserved -= actual_segments`
  - On the final run (`times_list == []`), refund any residual
    reservation (`schedule_complete_refund`)

**At cancel** (`schedules.cancel_schedule`):
- Refund any remaining `credits_reserved` (`schedule_cancel_refund`), set to 0, mark cancelled

**At edit** (`schedules.update_schedule`, #16):
- Reject if status is `cancelled` or `completed`
- Refund the old `credits_reserved` (`schedule_cancel_refund`)
- Re-estimate, debit the new reservation (`schedule_reserve`)
- If new-reserve raises `InsufficientCredits`, reverse the refund
  (`adjustment` debit) so the wallet is net-zero on failure
- Update fields, recompute `next_run_at`, commit, audit
- **Net wallet change = new - old (delta only if changed)**

**At delete** (`schedules.delete_schedule`, #16):
- Reject if `status == 'active'` (cancel first)
- Reject if `runs_completed > 0` (fired history must be preserved)
- Refund any remaining `credits_reserved`, hard delete the row

Why this shape rather than debit-at-fire: a school can schedule 500 SMS
for Wednesday, spend their balance on Monday, and the schedule still
fires on Wednesday because the credit was reserved. The `NULL` sentinel
preserves pre-#44 schedules that were created before this model existed.

## Single-write-gate pattern (working-style)

When a session must modify several files atomically (e.g. a feature
touching service + route + 2 templates + tests), the paste is structured:

1. Read all target files into memory.
2. Verify **all** anchor strings are present (throw → zero disk changes).
3. Apply **all** mutations in memory.
4. Verify the mutations are present in memory (throw → zero disk changes).
5. Write all files.
6. Verify the on-disk content.
7. Run tests.

Any `throw` before step 5 leaves the working tree untouched. This is the
fix for "throw in a pasted line doesn't stop later lines" — the mutation
is not reachable unless every prior guard passed.
