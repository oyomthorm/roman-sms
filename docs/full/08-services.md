# Part 7a — Services layer overview

Every business rule lives in `app/services/`. Routes, worker, and CLI
are thin glue — they parse input, call a service, and format output.
If a rule ever appears in a route or a model, it is a bug.

This is the reference for the **31 modules** in `app/services/`. Each
entry: purpose, key functions, what it touches, and (where relevant)
what it must not do.

**Note on `[VERIFY:]` markers.** Unlike the API reference (Part 6),
this file has almost none — the services and their behaviors are
described in `STRUCTURE.md` and `02-architecture.md`. Where a marker
does appear, it names the exact thing to check (typically an exact
parameter name that the diagrams abbreviated).

## 7a.1 The layering rule

    routes / api / worker / cli
        |
        v
    services   <-- every business rule
        |
        v
    models     <-- schema and convenience properties only
        |
        v
    Postgres

**Nothing enforces a rule twice.** If `check_can_send` lives in
`entitlements.py`, the route does not re-check subscription status,
the model does not validate wallet balance, and the worker does not
duplicate the guard. There is one place a rule lives; every consumer
calls it.

**Why this matters for maintenance.** When a rule changes (e.g. "low
balance threshold moves from 10 to 25 messages"), the change is in
one file. When a rule is duplicated, the change lands in one file and
the other copy silently disagrees. The layering rule exists to prevent
that class of bug.

**Transaction boundaries.** Services commit their own transactions
unless the caller explicitly opens one. `create_campaign`, `mark_paid`,
and `materialize_run` are single-transaction operations — the
campaign + wallet debit + log rows commit together, or not at all.
`create_schedule` and `update_schedule` are more intricate (they may
refund then re-reserve) and use explicit rollback-on-failure paths.
Reading a service should tell you exactly where its commits are —
every commit is a durability boundary.

## 7a.2 `wallet.py` — append-only ledger

**Purpose.** Every credit and debit in the system. Append-only — a
`WalletTransaction` row is never updated or deleted.

**Key functions:**

- `get_balance(org_id) -> int` — reads `SUM(delta)` from the ledger
- `credit(org_id, amount, source_org_id=None, reason=..., notes=None)`
  — appends a positive-delta row
- `debit(org_id, amount, reason=..., reference=None)` — appends a
  negative-delta row; raises `InsufficientCredits` if balance < amount
- `transfer(src_org_id, dst_org_id, amount)` — atomic debit + credit
  pair

**`EXTERNAL_CREDIT_REASONS`** — the enumerated set of valid `reason`
values for credits: `master_opening_balance`, `master_topup`,
`pahappa_sync`, `refund`, `adjustment`, `schedule_cancel_refund`,
`schedule_partial_refund`, `schedule_complete_refund`,
`schedule_overage_refund`, `plan_grant`. A credit with a `source_org_id`
is an internal transfer (must reference a real source); a credit
without must use one of the external reasons.

**Invariants:**

- `SUM(delta) == last.balance_after` — verified by
  `scripts/reconcile.py`
- Postgres `SELECT ... FOR UPDATE` on the org row during writes — SQLite
  would not serialize concurrent writes. Postgres is required in
  production for this reason.
- Debits are paired with a `reference` (e.g. `campaign:{id}`,
  `schedule:{id}`) so the ledger can be reconciled against the
  triggering event.

**What it must not do:** enforce business rules on *why* a debit is
allowed. `check_can_send` (in `entitlements.py`) is responsible for
whether the send is permitted; the wallet just moves the money.

## 7a.3 `billing.py` — invoices

**Purpose.** Invoice creation, plan snapshot, mark-paid transaction.

**Key functions:**

- `create_invoice(org, plan, actor)` — snapshots plan price and credits
  into a new `Invoice` row; status `pending`
- `mark_paid(invoice, actor)` — expires existing subscription, creates
  new subscription from invoice snapshot, credits wallet
  (`reason='plan_grant'`), flips invoice to `paid`
- `list_for_org(org)` — invoices visible to an org
- `list_all()` — master view
- `get_for_org(invoice_id, org)` — scoped get, returns `None` if
  outside org

**The invoice is the source of truth once issued.** PDF generation
reads the invoice row alone — no live Plan or Organization lookup — so
what the customer paid for is what the PDF shows, forever. If the
plan's price is changed after the invoice, the old invoice still shows
the old price. This is correct behavior: a plan change is a new
invoice, never a modification of the old one.

**Idempotency on mark-paid.** Marking an already-paid invoice is a
no-op (returns without error) — the operator cannot double-credit by
clicking twice.

## 7a.4 `entitlements.py` — the guards

**Purpose.** All "can this org/user do this?" checks, in one place.

**Key functions:**

- `check_can_send(org, total_segments)` — raises if org inactive,
  no active subscription, or wallet balance < total. Called by
  `campaigns.create_campaign` and `schedules.create_schedule`.
- `check_contact_limit(org, adding=1)` — raises if adding would exceed
  plan's contact cap
- `active_subscription(org_id)` — returns the Subscription or `None`
- `wallet_balance_ok(org, cost)` — balance-only variant, used in
  preview and estimate paths

**The single guard.** If a new "can they do this?" check is needed, it
goes here. Not in the route, not in the model, not in the worker — in
`entitlements.py`, called from the appropriate service.

## 7a.5 `subscriptions.py`

**Purpose.** Subscription lifecycle — create, expire, query.

**Key functions:**

- `create_from_invoice(invoice, org)` — called by `billing.mark_paid`
- `expire(org_id)` — marks existing subscription `expired`
- `get_active(org_id)` — returns the current active subscription
- `expire_stale()` — CLI/cron helper; expires subscriptions past their
  end date

**Rate limits** live on the subscription's plan snapshot, not on the
live plan — same reason as invoice: the plan can change, the customer's
limits cannot.

## 7a.6 `campaigns.py` — send-now flow

**Purpose.** The `POST /campaigns/new` handler's backing logic, plus
list/detail/cancel.

**Key functions:**

- `create_campaign(org, name, body, target, user, ...)` — the
  single-write-gate transaction. Resolves recipients, renders per-
  recipient body, computes segments, checks can-send, creates
  Campaign, debits wallet, creates MessageLog rows, queues SendQueue
  entry, commits.
- `list_for_org(org, user)` — department-filtered list
- `get_for_user(campaign_id, user)` — department-filtered get
- `cancel(campaign_id, user)` — sets status cancelled, stops pending
  sends (no refund — see 5.6 and backlog #16)

**The single-write-gate.** This is the most important service in the
system. Everything in `create_campaign` between the `db.session.flush()`
(for the Campaign ID) and the final `db.session.commit()` is one
transaction. If any step raises, rollback reverses the Campaign, the
wallet debit, the MessageLog rows, the SendQueue entry — everything.
The wallet and the campaign are always consistent.

**What it does not do:** it does not touch the schedule path. Schedules
are `schedules.create_schedule` for the reservation and
`schedules.materialize_run` for the fire. Two different flows, two
different services, one shared `renderer` and one shared
`entitlements.check_can_send`.

## 7a.7 `renderer.py` — message rendering

**Purpose.** Substitution and segment arithmetic.

**Key functions:**

- `render(org, body, contact) -> str` — substitutes `{{name}}` etc.
  from the contact and org context; prepends the brand prefix
- `render_personalized(org, body, vars) -> str` — substitutes
  arbitrary `{{column}}` from a dict (for CSV-personalized sends)
- `segments(body) -> int` — GSM-7 or UCS-2 segment count, including
  the brand prefix
- `substitute(template, vars) -> str` — the pure substitution step

**Segment arithmetic is critical.** Every cost computation in the
system (preview, reservation, actual fire, wallet debit) calls
`segments()`. If the counter on the campaign form and the server's
`segments()` diverge, the customer is charged the wrong amount. They
are kept in sync by convention — the JS counter mirrors the Python
function — but they are two separate implementations. A change to one
requires a change to the other.

## 7a.8 `dispatch.py` — worker job execution

**Purpose.** The send-queue drain. Called by `worker.py`.

**Key functions:**

- `claim_jobs(limit)` — `SELECT ... FOR UPDATE SKIP LOCKED` from
  SendQueue; returns job IDs
- `process_job(job_id)` — per-job: rate check, call Pahappa send,
  update MessageLog status, refund on failure, mark campaign complete
  on last message

**Rate limiting** is enforced here, not upstream. `ratelimit.py`
provides the per-minute and per-day checks against `MessageLog`
history. A batch never exceeds the minute budget; a daily cap
requeues for later.

**Failure handling.** A Pahappa send failure marks the MessageLog
`failed` and refunds that segment's credit. The rest of the campaign
continues. If the last message's status transition is the completion
trigger, the campaign is marked complete regardless of how many
failed — the outcome is "completed with N failures", not "failed".

## 7a.9 `schedules.py` — scheduled campaigns

**Purpose.** Schedule lifecycle — create, edit, delete, pause, resume,
cancel — and fire-time materialization.

**Key functions:**

- `create_schedule(org, ..., user)` — the pre-reservation transaction:
  validates times, resolves recipients, computes total segments, calls
  `check_can_send`, debits wallet with `schedule_reserve`, creates the
  row with `credits_reserved=total`
- `update_schedule(schedule_id, ...)` — refunds old reservation, debits
  new; net wallet change = new − old; rollback-safe if new reservation
  fails
- `delete_schedule(schedule_id, user)` — only allowed if
  `runs_completed == 0`; refunds and hard-deletes
- `pause(schedule_id)` / `resume(schedule_id)` — no wallet action;
  reservation stays
- `cancel_schedule(schedule_id)` — refunds remaining reservation,
  marks cancelled
- `claim_due_schedule()` — `SELECT ... FOR UPDATE SKIP LOCKED` for due
  schedules; returns the schedule ID and the specific time to fire
- `materialize_run(schedule_id, fired_iso)` — the fire-time logic:
  legacy path (debit at fire), #44 path (decrement reservation),
  overage guard (skip + refund + pause if actual > reserved),
  completion path (refund residual on last run)

**The claim → materialize split.** `claim_due_schedule` runs in the
worker tick's scheduler loop, holds the row lock briefly, computes
which time slot is due, removes it from `times_list`, and commits.
Then `materialize_run` runs on the claimed schedule — if the schedule
was cancelled between claim and materialize, the second step is a
no-op. This split exists so the row lock is held for the shortest
possible time.

**The #44 guard.** If `actual > credits_reserved` (contacts grew
between schedule create and fire), the run is skipped, the full
reservation is refunded, and the schedule is paused with a clear
reason. This is deliberate: a school should never be silently charged
more than they committed. If contacts shrink, the difference is
refunded at completion.

## 7a.10 `templates_svc.py` — message templates

**Purpose.** Template CRUD, department-filtered.

**Note the `_svc` suffix.** `templates.py` would shadow `app/templates/`
on import. Never rename it.

**Key functions:** `list_templates`, `get_for_user`, `create_template`,
`update_template`, `delete_template` — all taking `user=` for
department filtering.

## 7a.11 `groups.py`

**Purpose.** Contact-group CRUD, department-filtered.

**Key functions:** `list_for_org`, `get_for_user`, `create`, `update`,
`delete` — same department-filter pattern as templates.

**Delete behavior.** Hard delete; contacts' `group_id` is cleared.
Does not guard against schedules referencing the group (backlog #38 —
the orphaned `group_id` is a known issue).

## 7a.12 `contacts.py`

**Purpose.** Contact CRUD, CSV import with persistent reporting, opt-out.

**Key functions:**

- `list_for_org(org, user, filters)` — department-filtered list
- `get_for_user(contact_id, user)` — department-filtered get
- `create(org, name, phone, group_id, district_id, notes, user)` —
  normalizes phone, rejects duplicate phone within org
- `update(contact_id, ...)` — partial update
- `delete(contact_id, user)` — hard delete
- `import_csv(org, file_stream, user)` — the import workflow: read
  each row, normalize phone, skip on invalid/opt-out/duplicate,
  create the rest; records every skip in `ContactImportIssue`
- `get_import(import_id, user)` — retrieve import report
- `export_import_errors(import_id, user)` — CSV of skipped rows
- `opt_out(contact_id, user)` → calls `optout.propagate_opt_out(phone)`

**Phone normalization.** `phones.normalize_ug` converts `0771...`,
`+256771...`, `256771...` to a canonical form. This is the single
normalizer — every phone entry point calls it.

**Duplicate handling.** Duplicate within the same org is rejected on
create; duplicate in the import file is skipped and recorded as an
issue; duplicate with an existing DB row is skipped with an issue
row. Duplicates across orgs are allowed (a phone can exist in two
schools' contact lists).

## 7a.13 `orgs.py` — organizations and school users

**Purpose.** Org CRUD, user CRUD within an org, the protected-org
guard.

**Key functions:**

- `create_associate(name, slug, ...)` — master creates an org directly
- `update_associate(org_id, ...)` — with `_refuse_if_protected` guard
- `get_detail(org_id)` — org detail with users, wallet, subscriptions
- `list_users(org)` — school users
- `create_school_user(org, ..., role, department)` — role-department
  guard (`associate_admin` requires `department=None`)
- `update_school_user(user_id, ...)` — name, email, department
- `suspend_user(user_id, actor)` / `terminate_user` / `reactivate_user`
  / `delete_user` — all with self-guard and last-admin guard
- `get_user(user_id)` / `get_user_activity(user_id, org)` — detail
  page data
- `_refuse_if_protected(org_id)` — raises if org is master or system

**The guards.** Suspend/terminate/delete reject self. They also reject
the last active `associate_admin` — the school must always retain at
least one admin, or it cannot manage itself. The only recovery from
"all admins lost" is a master password reset.

**Protected orgs.** Org 1 (master) and org 2 (system) are never
editable via the form. Their slugs, names, and statuses are fixed for
platform mechanics.

## 7a.14 `plans.py`

**Purpose.** Plan CRUD.

**Key functions:** `create`, `list_all`, `update` (or is it immutable
after issuance? `[VERIFY: whether plans.update exists — the architecture
suggests plans are immutable once subscribed, but the master UI has
`/master/plans/<id>/edit`; see `06-api-web.md` §6a.20]`).

**Immutable-once-issued** is the design intent — the invoice snapshot
is what the customer paid for. But the master UI does expose an edit
form, which implies either (a) edits are allowed only for plans with
no active subscribers, or (b) edits are allowed and existing
subscriptions retain their snapshot. Check `plans.py` to confirm.

## 7a.15 `users.py`

**Purpose.** User authentication and password management.

**Key functions:**

- `authenticate(email, password)` — returns the User or `None`; used
  by both web and mobile login
- `change_password(user, old, new)` — validates old, updates hash
- `reset_password(user_id, actor)` — sets a temporary password and
  notifies the user
- `create_from_signup(...)` — internal, used by `signups.approve`

**Password hashing** uses `werkzeug.security.generate_password_hash`
(standard Flask). Not bcrypt, not argon2 — the Werkzeug default.
`[VERIFY: current algorithm and iteration count — check
users.create_from_signup or set_password]`.

## 7a.16 `signups.py`

**Purpose.** Public signup requests and the approval transaction.

**Key functions:**

- `submit_request(org_name, slug, contact_name, email, phone, address,
  vertical=None)` — validates and creates `SignupRequest`; sends
  acknowledgement email to applicant and notification to
  `ALERT_EMAIL`
- `list_requests(status=pending)` — master queue
- `get(request_id)` — detail
- `approve(request_id, actor, starter_credits, vertical)` — the
  multi-write transaction: create Organization, create initial
  `associate_admin` User, `wallet.transfer(master, new_org,
  starter_credits)`, flip request to `approved`, send welcome email
- `reject(request_id, actor, reason)` — flip request to `rejected`

**The approval transaction.** Everything in `approve` runs as one
transaction. If any step raises, rollback reverses the Organization,
the User, and the wallet transfer. The signup request remains pending.
This is the same single-write-gate discipline as `create_campaign`.

**The password-set link.** The initial admin user is created with a
random password hash; the welcome email contains a token that, when
used, sets a real password. Token expires in 24 hours.

## 7a.17 `pool.py`

**Purpose.** Master contact pool — grant/revoke, list, opt-out
propagation.

**Key functions:**

- `grant_permission(org, agreement_text, actor)` — creates
  `PoolPermission` row (agreement text verbatim), copies contacts into
  `PoolContact` rows with group/district/org snapshots
- `revoke_permission(org)` — deletes `PoolContact` rows for that org
- `list_pool_groups(filters)` — master view
- `propagate_opt_out(phone)` — called by every opt-out path; marks
  the phone opted out in the pool and in the platform OptOut table

**The snapshot model.** Pool contacts are a point-in-time copy — if
the source org renames a group or adds a contact, the pool does not
change. The only way to refresh is to revoke and re-grant. This is
deliberate — the pool is a pool, not a live view.

## 7a.18 `personalization.py`

**Purpose.** CSV-personalized campaign rendering (feature #33).

**Key functions:**

- `preview(org, body, csv_stream)` — returns per-row rendered output
  for the campaign form's preview (first N rows)
- `render_row(org, body, vars)` — wraps `renderer.render_personalized`

**Cost computation.** The total cost is the sum of per-row segments,
not `rows × template_segments` — because substitution changes length
per row. If `{{name}}` is "Alice" in one row and "Bartholomew" in
another, the segment counts differ.

## 7a.19 `chat.py`

**Purpose.** DM and broadcast channels, polling.

**Key functions:**

- `list_channels(user)` — channels visible to the user
- `get_channel(channel_id, user)` — scoped get
- `send(channel_id, body, sender)` — append a message
- `list_messages(channel_id, since=ts, user)` — polling read
- `mark_read(channel_id, user, last_read_message_id)` — read state

**Read state.** `ChatReadState` records the last read message ID per
user per channel. Updated on message list load, or on explicit
`mark_read` — `[VERIFY: which path is used in practice]`.

## 7a.20 `notifications.py`

**Purpose.** Live-computed notifications.

**Key functions:**

- `compute(org, user)` — returns the current notification list based
  on org state (low balance, plan expiring, no contacts, etc.)
- `dismiss(user, key)` — records `NotificationDismissal`

**No stored inbox.** A notification is recomputed on every render.
Dismissing one hides it; if the condition clears and later recurs,
the notification returns (possibly with a fresh key, so the prior
dismissal doesn't apply).

## 7a.21 `audit.py`

**Purpose.** Append-only audit log.

**Key functions:**

- `log(actor, action, target, details=None)` — appends an `AuditLog`
  row; commits its own transaction; **swallows exceptions** (a failed
  audit write does not fail the caller)
- `list_for_target(target_type, target_id)` — audit history for a
  specific target
- `list_all(filters)` — master view

**Append-only.** No row is ever updated or deleted. This is the source
of truth for "what happened" queries.

**The swallow-on-error behavior** is a known design trade-off. Audit
is best-effort, not transactional. A caller who requires audit
completeness wraps their own transaction and verifies the row exists
after. See `02-architecture.md` §2.17 note.

## 7a.22 `mailer.py`

**Purpose.** Outbound email — welcome, password reset, notifications,
completion emails.

**Key functions:**

- `send_welcome(to, set_password_link)` — signup approval
- `send_password_reset(to, reset_link)` — user-initiated reset
- `send_campaign_complete(to_list, campaign)` — completion notification
- `send_audit_alert(to, details)` — internal

**SMTP config.** Mailgun on port 2525 — DigitalOcean blocks 25/465/587
permanently. This is a platform constraint, not a preference. See
`RUNBOOK.md` for SMTP troubleshooting.

## 7a.23 `optout_links.py`

**Purpose.** One-click opt-out links from SMS messages.

**Key functions:**

- `opt_out(phone)` — public form submission
- `consume(token)` — one-click link consumption; resolves token to
  phone, calls propagate
- `create_token(phone)` — for embedding in messages

**Token scope.** Tokens are single-use. Consuming an already-consumed
token re-shows the confirmation without changing state.

## 7a.24 `password_reset.py`

**Purpose.** User-initiated password reset via email.

**Key functions:**

- `request(email)` — creates a reset token, sends email; returns
  neutrally whether the email exists (security: don't reveal account
  existence)
- `consume(token, new_password)` — validates token, sets password

**Token lifetime** — 24 hours, matching the initial set-password link.

## 7a.25 `campaign_notifications.py`

**Purpose.** Completion emails when a campaign finishes.

**Key functions:**

- `notify_complete(campaign)` — deduplicated recipient list = campaign
  creator + every active `associate_admin` in the org; sends via
  `mailer.send_campaign_complete`

## 7a.26 `geo.py`

**Purpose.** Ugandan districts.

**Key functions:**

- `list_districts()` — all districts, cached
- `get_district(id)` — by ID
- `seed_districts()` — CLI helper; populates the `district` table

Districts are seeded once, rarely change.

## 7a.27 `pahappa_balance.py`

**Purpose.** Query Pahappa's (EgoSMS) balance.

**Key functions:**

- `get_provider_balance()` — returns Pahappa's account balance; used
  by CLI `flask egosms-balance` and the ops dashboard

**Not the same as wallet balance.** Pahappa's balance is what the
platform has prepaid to the upstream provider. The wallet balance is
what customers have paid the platform. Two separate accounts; the
relationship between them is a business decision, not a technical
one. Backlog #32 is a known drift fix between the two.

## 7a.28 `ratelimit.py`

**Purpose.** Per-org rate limit enforcement.

**Key functions:**

- `check_rate(org, batch_size)` — raises if the batch would exceed
  minute or daily budget
- `minute_budget_remaining(org)` / `daily_budget_remaining(org)` —
  query helpers

**Data source.** Counted from `MessageLog.status='sent'` with
timestamps. No separate counter table — the log is the counter.

## 7a.29 `invoice_pdf.py`

**Purpose.** Invoice PDF generation.

**Key functions:**

- `render(invoice)` — returns PDF bytes from the invoice snapshot
  alone

**Constraint.** No live Plan or Organization lookup. The invoice row
is the only input. This is what makes the PDF reproducible a year
later.

## 7a.30 `templates_svc.py` — see §7a.10

(Repeated here for completeness of the module list — see the full
entry above.)

## 7a.31 `phones.py`

**Purpose.** Phone normalization and pasted-number parsing.

**Key functions:**

- `normalize_ug(raw) -> str | None` — Ugandan phone canonicalization;
  returns `None` for unparseable input
- `parse_pasted_numbers(text) -> list[str]` — parses up to 500 pasted
  numbers, deduped, normalized

**Formatting.** Uganda country code 256, national formats `07XX...`
and `2567XX...` are the standard. The normalized form is
`256XXXXXXXXX` (no `+`). `[VERIFY: exact canonical format — check
`normalize_ug` return value]`.

## 7a.32 How services interact — a worked example

Creating a send-now campaign, traced through every service it touches:

    POST /campaigns/new
      -> campaigns.create_campaign
           -> renderer.render (per recipient)
           -> renderer.segments (per recipient, summed)
           -> entitlements.check_can_send
           -> contacts.list_for_org (recipient resolution)
           -> wallet.debit (reason='sms_send', reference=f'campaign:{id}')
           -> audit.log (implicit, if enabled on campaign create)
           -> db.session.commit

    Worker tick (every ~10s):
      -> dispatch.claim_jobs
           -> dispatch.process_job
                -> ratelimit.check_rate
                -> (Pahappa API call)
                -> campaign_notifications.notify_complete (on last)

    Pahappa webhook:
      -> webhooks.handle_transaction_status
           -> MessageLog.status = 'delivered' | 'delivery_failed'

    Cancel (if before all sent):
      -> campaigns.cancel
           (no wallet refund today — backlog #16)

Every arrow is a service call. No route or worker ever mutates a model
directly. That's the whole point.

## 7a.33 Adding a new service (checklist)

1. New module in `app/services/<concern>.py`.
2. Name it after the concern, not the caller. `billing.py`, not
   `invoices_route_helper.py`.
3. If it collides with `app/templates/`, use the `_svc` suffix (see
   `templates_svc.py`).
4. Every function that reads tenant data takes `org` or `user=`
   explicitly. Never read `current_user` from within a service.
5. If the function commits, name the transaction boundary in the
   docstring. "This function commits X and Y together" is a useful
   statement; "commits as needed" is not.
6. If the function can raise, name the exceptions it raises (e.g.
   `InsufficientCredits`, `OrgProtected`).
7. Add unit tests in `tests/unit/test_<concern>.py` — service-level,
   no HTTP.
8. Document it here in Part 7a.

---

*Part 7a of 10. See `08b-models.md` next.*