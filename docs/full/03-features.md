# Part 3 — Features in detail

Every feature that has shipped in the platform, in the order it was
built, with the problem, the design, and the tradeoffs.

## 3.1 Personalized campaign sends (#33, prior session)

**Problem.** Schools need per-recipient messages, not one blanket body.
"Dear Alice, your daughter Mary's fee balance is UGX 45,000, due
20 Nov. Pay via USSD: *165*3*...". One body to 500 parents cannot
include each parent's name or balance.

**Design.**
- CSV upload with arbitrary columns (`name`, `phone`, `balance`,
  `due_date`, ...).
- Template body uses `{{column}}` placeholders.
- `renderer.render_personalized(org, body, vars)` substitutes per-row.
- Recipient count and cost computed as **sum of per-row segments**,
  not `rows × template_segments` — because substitution changes length.
- Per-row rendered body stored on `MessageLog.body` (schema unchanged —
  `MessageLog.body` already stored the final text).
- Web-only. Mobile deferred.

**Files:** `services/personalization.py`, `renderer.render_personalized`,
`routes/campaigns.py::personalized_new`, `personalized_preview`.
UI: third radio on `/campaigns/new` ("Personalized (CSV)"), live
preview via `/campaigns/personalized/preview`, gated submit button.

**Tradeoffs.** (+) Schools get personalized sends. (+) No schema change
needed. (−) Web-only. (−) The USSD payment line is a follow-up
(decide whether it's a CSV column or a per-org default).

## 3.2 Department isolation (A1–A5)

**Problem.** Schools wanted each department (bursar, DOS, dean, HT) to
see only their own data — but not complete isolation. The HT needs to
see everything. The bursar needs to see their department's records plus
shared records, never the DOS's.

**Design.** Five-table `department` column + one filter function (see
§2.3). Every read service applies `department_filter`. Every create
service sets `record.department = current_user.department`. No route
accepts `department` from the form.

**Migration:** `e5997cc4f270` (A1) — 5 columns, nullable, indexed.
**Service layer:** A2. **Route layer:** A3a–A3d. **UI:** A4.
**School-admin user CRUD:** A5 (`/school/users` — list, create, edit,
delete, reset password, department dropdown).

**Tradeoffs.** (+) Department isolation is correct by construction. (+)
One filter to audit. (−) The school admin cannot pre-seed a bursar's
data; the bursar must create it. Deliberate — nobody assigns data to a
department they aren't in. If it becomes a pain point, revisit with a
"set department for other users" feature.

**See:** ADR-026, `docs/DEPARTMENTS.md` (Q1/Q2/Q3 workflow guide).

## 3.3 User lifecycle (#46)

**Problem.** When a user leaves a school, the admin had only two
options: keep them active, or delete them (destroys audit attribution
and chat context). Neither is correct for "this person no longer works
here."

**Design.** `user.status` field (active/suspended/terminated). Suspend
allows login but blocks new sends (checked at `/campaigns/new`).
Terminate blocks login (`is_active_flag=False`). Reactivate restores.
Guards: cannot suspend/terminate self, cannot suspend/terminate the
last active associate_admin in the org.

**Migration:** `e37cc1348332`.
**Files:** `services/orgs.py::suspend_user`, `terminate_user`,
`reactivate_user`, `routes/school.py::user_suspend`, `user_terminate`,
`user_reactivate`, `routes/auth.py` (terminate check via
`is_active_flag`), `routes/campaigns.py::new` (suspend check).

**Tradeoffs.** (+) One field, one check (`status != 'active'`). (+)
Login and send enforcement can differ. (−) `is_active_flag` / `status`
sync is redundant, but rewriting Flask-Login's dependency is a larger
blast radius. See ADR-024.

## 3.4 Organization.vertical (#45)

**Problem.** The platform is built for Ugandan schools. The first
paying customer outside that vertical (ORONEK) still works, but the UI
is school-centric. Departments ("Bursar / DOS / Dean / HT") don't map
to a general business.

**Design.** `organization.vertical` (school/business/NULL). Master-only.
Set at signup approval via radio buttons. Editable on org form. Never
shown to the school's own users. No permissions or filters depend on
it today; its purpose is onboarding copy (deferred — #51) and analytics.

**Migration:** `87cd66d8578c`.
**Files:** `services/orgs.py` (`create_associate`, `update_associate`
accept `vertical=`), `services/signups.py::approve`, `routes/master.py`
(form reads), templates on `/master/signups/<id>` and
`/master/orgs/<id>/edit`.

**Tradeoffs.** (+) Foundation for vertical-aware UX without a future
schema change. (+) Zero behavioral change to existing customers (all
NULL after migration). (−) Until #51 ships, the field is inert. See
ADR-025.

## 3.5 Schedule pre-reservation of credits (#44)

**Problem.** Before #44, a scheduled campaign debit-ed the wallet at
fire time, per run. A school could schedule 500 SMS for Wednesday,
spend their balance on Monday, and on Wednesday the run would silently
fail. The school had done everything asked of them.

**Design.** Reserve the total upfront.

At create:
- Estimate recipients, compute `segments_per_run`, total = segments ×
  len(times).
- `check_can_send(org, total)`, then `wallet.debit(org.id, total,
  reason='schedule_reserve')`.
- Store `credits_reserved = total` on the row.

At fire:
- **Legacy** (`credits_reserved IS NULL`): old behavior, debit at fire.
- **New**: skip check_can_send, skip wallet.debit. Decrement
  `credits_reserved` by actual.
  - `actual > credits_reserved` → skip run, refund fully
    (`schedule_overage_refund`), pause schedule with clear reason.
  - `actual < credits_reserved` → fire normally, refund difference at
    completion (`schedule_complete_refund`).

At cancel: refund remaining, set `credits_reserved=0`.

**Migration:** `c41928d919da`.
**Files:** `services/schedules.py::create_schedule`,
`materialize_run`, `cancel_schedule`, `claim_due_schedule`,
`services/wallet.py` (`EXTERNAL_CREDIT_REASONS` extended),
`app/models/scheduling.py::CampaignSchedule.credits_reserved`.

**Tradeoffs.** (+) A schedule is a commitment. The school's balance
cannot silently break a scheduled send. (−) The school pays upfront for
all future runs; available balance is lower during the schedule's
lifetime. See ADR-023, ADR-027.

## 3.6 Schedules CRUD (#16)

**Problem.** Before #16, editing a scheduled campaign required
cancelling (refunds) and re-creating (debits). That's a real UX gap:
if there's a typo in the message, cancel+re-create is two operations.

**Design.** Edit times, body, name, and recipient filters after
creation. The reservation adjusts automatically:
- Refund old `credits_reserved` (`schedule_cancel_refund`).
- Re-estimate, debit new (`schedule_reserve`).
- If new-reserve raises InsufficientCredits, reverse the refund so
  wallet is net-zero on failure.
- Net wallet change = new - old (delta only if changed).

Delete: only if never fired and not active. Refund remaining
reservation, hard delete the row.

**Files:** `services/schedules.py::update_schedule`,
`delete_schedule`, `routes/campaigns.py::schedule_edit`,
`schedule_delete`, `templates/campaigns/schedule_edit.html` (new form),
`schedule_detail.html` (Edit + Delete buttons, "Credits held" stat
card), `schedules.html` (Edit link per row).

**Tradeoffs.** (+) One operation instead of two. (+) Reservation stays
correct. (−) Two code paths in `update_schedule` when the wallet
reserve fails (refund then reverse).

## 3.7 User detail page (#47)

**Problem.** School admins wanted to see what a specific user has been
doing: "How many campaigns has the bursar sent this term?" The
`/school/users` list shows the user but not their activity.

**Design.** `GET /school/users/<id>` — read-only activity summary.

- Identity card: email, name, status badge, role, department, created
  date, last login.
- Four stat cards: campaigns (all-time), campaigns (30d), active
  schedules, audit events.
- Recent campaigns table (last 10, links to detail).
- Recent schedules table (last 10, links to detail).
- Recent audit activity (last 20 events where `actor_id = user.id`).

**Files:** `services/orgs.py::get_user`, `get_user_activity`,
`routes/school.py::user_detail`, `templates/school/user_detail.html`
(new). Link added: `users.html` email column now links to detail.

**Tradeoffs.** (+) School admins get the activity view. (+) No schema
change. (−) Doesn't show chat messages or pool contributions (deferred
— low value for admins today).

## 3.8 Other shipped features (prior sessions)

### Scheduled campaigns (0.8.0)

Days-of-week and time-of-day rule, plus start/end date. Materialized by
the worker. See ADR-003, ADR-015.

### Character / segment / cost counter (0.8.1)

Live JS counter on the campaign form, mirrors the server's segment
arithmetic, includes the brand prefix (per ADR-013). See ADR-013.

### Paste-numbers recipient source (0.8.1)

Up to 500 pasted phone numbers as a send target. Skips opt-outs, skips
duplicates. See ADR-014.

### Invoice PDF export (0.9.0)

PDF from Invoice row snapshot alone (no live Plan/Org lookups). See
§2.7.

### Campaign completion emails (0.9.0)

When a campaign finishes, email creator + every active
associate_admin, deduplicated. See ADR-008.

### Dashboard usage charts (0.9.0)

30-day trend, sent/delivered/failed counts, avg daily spend. Inline SVG.
See ADR-016.

### Contact import with persistent reporting (0.11.0)

Upload CSV → preview → categorize every skipped row → persistent report
at `/contacts/imports/<id>` with filter tabs + downloadable error CSV.
See ADR-011.

### Master contact pool (0.7.0)

Per-associate opt-in, agreement snapshot, revocable. Cross-org pool
campaigns from the system sender. See ADR-007.

### Delivery webhook (0.5.0)

Pahappa POSTs delivery reports; webhook flips `MessageLog.status` to
`delivered` or `delivery_failed`. See ADR-009.

### Chat (0.6.0)

DM (master ↔ one associate) + broadcast. 3-second polling.

### Notifications (0.6.0)

Computed on every render from live conditions. Per-user dismissals. See
ADR-008.

### Mobile API (0.12.0)

`/api/v1/*` — JSON surface for Flutter. See Part 6.

---

*Part 3 of 10. See `04-user-guide-master.md` next.*