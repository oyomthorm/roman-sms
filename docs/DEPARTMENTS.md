# Department Isolation — Workflow Guide

> Last reviewed: 2026-11-10
> Status: implemented end-to-end (A1 schema, A2 service, A3 route, A4 UI).
> This document is the reference for how schools and departments are meant to work in Roman SMS.

Roman SMS is a multi-tenant SMS platform for Ugandan schools. Every school is one **organization** (org). Within a school, users can be scoped to a **department** — bursar, DOS (Director of Studies), dean, HT (Head Teacher), or "shared" (department = NULL, meaning they see everything in the school).

This document specifies:
1. Who manages whom (Q1)
2. Who pays (Q2)
3. When and how SMS credits are debited (Q3)
4. What department isolation means at the UI, route, and DB layers
5. What is NOT in scope today (deferred features)


## 1. Who manages school users

**Answer: each school's own administrator manages their school's users. Master admin does not create school users.**

### Roles

| Role | Where they live | What they can do |
|---|---|---|
| **master_admin** | master org (Roman SMS) | Platform operator. Manages orgs, plans, invoices, wallet grants, signup approvals. **Does not create school users.** Sees all users across all orgs (read-only in `/master/orgs/<id>`). |
| **associate_admin** (school admin) | any school org | **Creates, edits, deletes users within their own org.** Assigns departments. Resets passwords. **Sees everything in their org** (department = NULL). |
| **associate_admin with a department set** | any school org | Rare. Same permissions as school admin but scoped to their department only for data views. **Cannot manage users** — user management is org-admin-only. |
| **Any other role with department set** (e.g. bursar as associate_admin) | any school org | Sees only groups/templates/campaigns/schedules scoped to their department + shared. Cannot manage users. |

### Permission matrix

| Action | master | org admin (dept=None) | dept-scoped user |
|---|---|---|---|
| Create a school user | ❌ | ✅ (own org) | ❌ |
| Edit a school user (name, email) | ❌ | ✅ (own org) | ❌ |
| Change a user's department | ❌ | ✅ (own org) | ❌ |
| Reset a user's password | ❌ | ✅ (own org) | ❌ |
| Delete a school user | ❌ | ✅ (own org) | ❌ |
| View school users in `/master/orgs/<id>` | ✅ (read-only) | (via own school's UI) | ❌ |
| Create groups/templates/campaigns | ✅ (any org, via master console "act as") | ✅ (own org) | ✅ (own dept + shared) |

**Consequence:** master creates an org + the initial `associate_admin` via signup approval. After that, the school manages its own users. If a school loses its admin, master can reset their password (existing `user_reset_password` route in `/master/orgs/<id>`) and the admin regains access.

### Department semantics

- **`department = None`** — the user sees **all** records in the org, regardless of their department. This is the "HT sees everything" model.
- **`department = 'bursar'`** — the user sees only records where `department = 'bursar' OR department IS NULL`. Never sees DOS/dean/HT-scoped data. Cannot create DOS-scoped data (the form doesn't offer it).
- **`department` on a record** — set at record creation time from `current_user.department`. A dept-scoped user creates dept-scoped records. An org admin (dept=None) creates **shared** records (`department = NULL`), which everyone can see.

**The rule:** *A user can create records scoped to their own department, or shared. Never to another department's scope.*


## 2. Who pays

**Answer: the organization pays, not the user. One wallet per school. Departments share the wallet. Master assigns plans.**

### Current model

- Every org has one wallet (see `wallet_transaction` table, keyed by `org_id`).
- Every SMS debit is `wallet_svc.debit(org_id, ...)`. The user who sent is recorded via `actor_id`, but the balance is the org's.
- **Departments do not have separate budgets.** A bursar sending a message and an HT sending a message both debit the same balance.

### Who can top up / buy a plan

| Action | master | org admin | dept-scoped user |
|---|---|---|---|
| View wallet balance (`/billing/wallet`) | ✅ | ✅ (own org) | ✅ (own org) |
| View invoices (`/billing/invoices`) | ✅ (all) | ✅ (own) | ✅ (own) |
| Assign a plan (`/master/orgs/<id>/assign_plan`) | ✅ | ❌ | ❌ |
| Grant credit (`/master/orgs/<id>/grant`) | ✅ | ❌ | ❌ |
| Issue invoice (`/master/orgs/<id>/new_invoice`) | ✅ | ❌ | ❌ |
| Mark invoice paid | ✅ | ❌ | ❌ |
| Sync to Pahappa | ✅ | ❌ | ❌ |

**Today, only master can transact credits.** Schools cannot buy SMS themselves through the platform — they contact the operator, who assigns a plan or grants credits manually.

### Why this model (and when to change it)

**This is intentional for the current sales motion.** Small Ugandan schools typically purchase via phone or invoice; the sales relationship is manual and doesn't benefit from self-service yet.

**When to revisit (`#43` in backlog):**
- Multiple schools request self-service plan purchase.
- You want a public signup → immediate plan → immediate SMS flow without master intervention.
- You're scaling to 20+ schools where manual plan assignment becomes an operational bottleneck.

**When that happens, the design is:**
- Add `POST /billing/plans/purchase` — associate_admin submits plan ID, invoice created, credits granted on payment.
- Master's `grant` and `assign_plan` routes remain as override tools.
- Payment integration (mobile money, bank transfer reconciliation) is a separate workstream.


## 3. When SMS credits are debited

**Answer: debited immediately at campaign send and at schedule creation. Refunded if the schedule is cancelled before it fires.**

### Current state (as of A4)

**Campaign (send-now):** `wallet_svc.debit(...)` is called inside `services/campaigns.py::create_campaign`, at the moment the campaign is queued. Recipient count is computed at that moment. No refunds — once queued, credits are consumed (unless the campaign is cancelled before dispatch, which currently refunds nothing — see "Known gaps" below).

**Schedule (send-later):** *currently debits at fire time, not creation time.* This is changing in `#44`.

### Target state (after #44)

- **At `create_schedule`:** compute recipient count from the current contact list (same logic `materialize_run` will use). Compute total segments. `wallet_svc.debit(org_id, total_segments, reason='schedule_reserve', reference=f'schedule:{schedule.id}')`. Store `credits_reserved` on the schedule row.
- **At `materialize_run`:** **do not debit again.** The credit was reserved. The worker creates the Campaign with `prepaid=True` (or similar) so `create_campaign` skips its own debit.
- **At `pause`:** no wallet action. Reservation stays held.
- **At `resume`:** no wallet action. Reservation stays held.
- **At `cancel`:** `wallet_svc.credit(org_id, credits_reserved, reason='schedule_cancel_refund', reference=f'schedule:{schedule.id}')`. Mark the schedule cancelled.
- **At completion:** no refund (credits consumed as intended).
- **If actual recipients > reserved** (contacts grew): **fail the schedule with a warning to the org admin** ("Schedule X had N more recipients than reserved. Increase the schedule's target or re-create with current contacts."). Do not silently debit more.
- **If actual recipients < reserved** (contacts shrank): refund the difference. `wallet_svc.credit(org_id, reserved - actual, reason='schedule_partial_refund')`.

### Why pre-reservation

Without pre-reservation, a school can schedule 500 SMS for next Wednesday, spend their balance by Monday on a bursar's ad-hoc campaign, and on Wednesday the scheduled send silently fails (or skips) because there's no credit. **The school scheduled the message; they expect the credit to be there.**

Pre-reservation turns "schedule" into a **commitment**: credit is debited now, message sends on schedule, no surprise failure. Cancel = credit returns. This is the correct behavior for a school's budget.

### Known gaps (backlog)

- **Campaign cancellation (`#16`) — refund behavior not yet specified.** When a send-now campaign is cancelled before all messages are sent, should the un-sent segments be refunded? The worker processes messages one at a time; a partially-sent campaign has consumed some credit. **Design decision deferred to #16.**
- **`#44` — schedule pre-reservation not yet implemented.**
- **`#43` — self-service plan purchase not yet implemented.**


## 4. Department isolation — implementation layers

For developers and operators maintaining the system.

### Database (A1 — migration `e5997cc4f270`)

Five tables have a `department` column (String(40), nullable, indexed):
- `user.department`
- `contact_group.department`
- `message_template.department`
- `campaign.department`
- `campaign_schedule.department`

All rows default to `NULL` (shared). No backfill required for existing data.

### Service layer (A2 + A3 + A4)

- `app/permissions.py::department_filter(query, model, user)` — the single filter used everywhere. Returns the query unchanged if `user is None` or `user.department is None`. Otherwise adds `WHERE (model.department = user.department OR model.department IS NULL)`.
- `list_for_org` and `get_for_user` helpers in `campaigns_svc`, `groups_svc`, `templates_svc`, `schedules_svc` — the read path for each model. `list_for_org` applies `department_filter`. `get_for_user` returns None for cross-department IDs (which the route turns into a 404).
- `create` / `create_template` / `create_campaign` / `create_schedule` — each accepts a `user=` parameter. The route passes `current_user`. The service sets `department=user.department` on the created row (or `None` if `user` is `None`).

### Route layer (A3)

Routes pass `user=current_user` to every service call:
- `routes/groups.py::index()` — `list_groups(org, user=current_user)`
- `routes/groups.py::new()` — `create(..., department=current_user.department)`
- `routes/groups.py::detail/edit/delete` — `get_for_user(...)`, 404 if `None`
- `routes/templates.py::index/new/edit/delete` — same pattern
- `routes/campaigns.py::index` — `list_for_org(org, user=current_user)`
- `routes/campaigns.py::new` — `create_campaign(..., user=current_user)`
- `routes/campaigns.py::detail/cancel` — `get_for_user(...)`, 404 if `None`
- `routes/campaigns.py::schedules/schedule_detail/pause/resume/cancel` — same pattern

**No route accepts a `department` from the form.** The department is always `current_user.department`. A user cannot create data scoped to another department. This is a security invariant, not an accident.

### UI layer (A4)

- **Group create/edit form** (`templates/groups/form.html`) — displays the current user's department as a read-only field. Helper text explains who will see the record.
- **Template create/edit form** (`templates/templates/form.html`) — same.
- **Profile page** (`templates/profile/index.html`) — shows the user's own department, read-only.
- **Master org detail** (`templates/master/org_detail.html`) — the Users table has a Department column showing each user's department. Master can see departments but cannot change them (per Q1).

### What "department-aware" means for the user

A user logged in as `bursar` sees:
- All groups/templates/campaigns/schedules where `department = 'bursar'` (created by other bursars in the same school)
- All groups/templates/etc. where `department = NULL` (created by org admins, or imported by the migration)
- **NOT** records where `department = 'dos'`, `'dean'`, or `'ht'`

A user logged in as org admin (`department = None`) sees everything. Every record they create is `department = NULL` (shared). To create a bursar-scoped group, they must log in as the bursar (or the bursar must create it themselves).

**Trade-off to be aware of:** an org admin cannot "pre-seed" a bursar-scoped group. If the school's admin wants to prepare groups for the bursar before the bursar logs in, they can't — the bursar must create them. This is a deliberate design choice (nobody assigns data to a department they're not in). If this becomes a pain point, revisit by allowing org admins to set the department on the create form. That change requires a route change (accept `department` from form only for org admins) and a security review. **Not currently planned.**


## 5. What is NOT in scope today

Deferred items in the backlog:

- **Per-department budgeting** — one wallet per school, departments share. Not on the roadmap unless requested.
- **Self-service plan purchase** (`#43`) — master-only today.
- **Master creating school users** — school admins do this. If a school loses all admins, master resets the existing admin's password via `/master/orgs/<id>`.
- **Editable department on `/profile`** — read-only today. User changes go through the school admin.
- **Cross-school assignment** — a user belongs to one org. No "user in two schools" feature.
- **Department-scoped billing** — invoices and wallet are org-level, not department-level.
- **Schedule pre-reservation of credits** (`#44`) — implemented in the next session; until then, schedules debit at fire time (existing behavior).
- **Schedule CRUD** (`#16`) — pause/resume/cancel work today; edit-scheduled-times and edit-body do not. List pages display schedules but do not offer edit or delete.

## 6. Verification — what "department isolation works" means

For QA and future contributors. The A5 verification (2026-11-10) proved:

- Bursar logs in, sees only their department's + shared groups/templates/campaigns/schedules.
- Bursar creates a group via UI → group row has `department = 'bursar'` on disk (verified via SQL).
- Org admin logs in, sees all groups/templates/campaigns/schedules.
- Attempting to view a cross-department record (via guessed URL) → 404 (not 403, to avoid leaking existence).
- All 189 tests pass, including 13 department-filter unit tests.

**Not yet verified in a real browser session** (backlog #40):
- The excluded items are not shown in the list pages (unit-tested, not UI-tested).
- Master's Users table shows department (A4 — should be verified in next deploy).

Future contributors: **run a manual browser test when touching any of the following:**
- `app/routes/groups.py`, `app/routes/templates.py`, `app/routes/campaigns.py` — all data-visibility changes.
- `app/templates/groups/`, `app/templates/templates/`, `app/templates/profile/` — all display changes.
- `app/services/permissions.py` — the single filter. Changing this breaks isolation.
- `app/services/schedules.py` — the worker is the second consumer of department logic (via `materialize_run`).