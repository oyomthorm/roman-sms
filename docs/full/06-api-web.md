# Part 6a — Web route reference (HTML blueprints)

This is the reference for the **HTML surface** — every blueprint under
`app/routes/`, the URLs they serve, the templates they render, and the
permissions that gate them. If you are looking for the mobile JSON API,
read `07-api-mobile.md` instead.

The web app is the primary interface — master console, associate
console, landing pages, public opt-out, webhooks. Mobile is a third
consumer of the same services (see §6a.1).

## 6a.1 What this reference covers, and what it doesn't

**What it covers** — every URL under every blueprint, the auth
requirement (`@master_required`, `@login_required`, `@org_admin_required`,
or none), which service the route calls, and what kind of response it
returns (HTML render, redirect, JSON, file download, error).

**What it does not cover** — the exact form field names, the exact
`name` attributes on each `<input>`, or the exact flash message strings.
Those are readable from the template or the handler. For a route
reference, the route path, auth gate, and service call are what
matters. Where field names would be useful, `[VERIFY from handler: …]`
points at the source.

**Where the business rules live** — in the service layer, never in
the route. A route is HTTP glue: parse the form, call the service,
render the result. If you want to know *what* an action does, read the
service; if you want to know *how it's triggered*, read the route.

**Three layers of enforcement** (from `PERMISSIONS.md`):

1. **Route decorator** — `@master_required`, `@org_admin_required`, or
   `@login_required`. Blocks the handler entirely.
2. **Query scoping** — every read goes through `org_scoped(Model)`.
3. **Service guard** — `check_can_send`, `check_contact_limit`,
   `orgs._refuse_if_protected`. Blocks the action even if the route
   let it through.

Any reference below that says "master-only" means layer 1. Any that
says "org-scoped" means layer 2. Any that says "service-guarded"
means layer 3.

## 6a.2 Blueprint inventory

18 HTML blueprints, each registered in `app/__init__.py` via
`app.register_blueprint(...)`:

| # | Blueprint | Prefix | Module | Handlers (approx) |
|---|---|---|---|---|
| 1 | `auth` | `/auth` | `routes/auth.py` | login, logout, signup redirect, password reset |
| 2 | `dashboard` | `/dashboard` | `routes/dashboard.py` | index |
| 3 | `contacts` | `/contacts` | `routes/contacts.py` | list, new, detail, edit, delete, import, import report, optout |
| 4 | `groups` | `/groups` | `routes/groups.py` | list, new, detail, edit, delete |
| 5 | `campaigns` | `/campaigns` | `routes/campaigns.py` | list, new, detail, cancel, personalized preview, schedules (list/detail/new/edit/delete/pause/resume/cancel) |
| 6 | `chat` | `/chat` | `routes/chat.py` | channel list, channel detail, send message, poll |
| 7 | `billing` | `/billing` | `routes/billing.py` | wallet, invoices, invoice detail |
| 8 | `reports` | `/reports` | `routes/reports.py` | delivery and usage summaries |
| 9 | `profile` | `/profile` | `routes/profile.py` | view, change password |
| 10 | `school` | `/school` | `routes/school.py` | user list, create, edit, detail, suspend, terminate, reactivate, delete, reset-password |
| 11 | `settings` | `/settings` | `routes/settings.py` | org settings, pool enable/disable |
| 12 | `notifications` | `/notifications` | `routes/notifications.py` | list, dismiss |
| 13 | `public` | `/` | `routes/public.py` | opt-out landing, opt-out POST, password reset (unauthenticated) |
| 14 | `signup` | `/signup` | `routes/signup.py` | request form, submit (unauthenticated, CSRF-protected, rate-limited) |
| 15 | `templates` | `/templates` | `routes/templates.py` | list, new, detail, edit, delete |
| 16 | `landing` | `/` | `routes/landing.py` | homepage |
| 17 | `webhooks` | `/api/webhooks` | `routes/webhooks.py` | Pahappa delivery status webhook (token-authenticated) |
| 18 | `master` | `/master` | `routes/master.py` | 25+ handlers — see §6a.20 |

## 6a.3 `auth` — `/auth`

| Method | Path | Auth | Handler → Service | Response |
|---|---|---|---|---|
| GET | `/auth/login` | none | render login form | HTML |
| POST | `/auth/login` | none | `users.authenticate(email, password)` | redirect to `/dashboard` or `/master`, flash on failure |
| POST | `/auth/logout` | login required | clear session | redirect to `/auth/login` |
| GET | `/auth/password-reset` | none | render request form | HTML — `[VERIFY: exact route path]` |
| POST | `/auth/password-reset` | none | `password_reset.request(email)` — emails a reset link | redirect to login with neutral flash |
| GET | `/auth/password-reset/<token>` | none | validate token, render set-password form | HTML |
| POST | `/auth/password-reset/<token>` | none | `password_reset.consume(token, new_password)` | redirect to login |

**Terminate guard:** the login handler checks `user.is_active_flag`.
A user with `status='terminated'` (per `02-architecture.md` §2.4) has
`is_active_flag=False` and cannot log in. The check is at login, not
at request time — an existing session survives termination until the
user logs out.

## 6a.4 `dashboard` — `/dashboard`

| Method | Path | Auth | Handler → Service | Response |
|---|---|---|---|---|
| GET | `/dashboard` | login required | `dashboard.compute(org)` | HTML — usage stats, wallet, trend |

The dashboard is org-scoped: master sees master-org stats, associate
sees their own org's. Cross-org aggregate is at `/master` only. See
`05-user-guide-school.md` §5.3 for the metric definitions.

## 6a.5 `contacts` — `/contacts`

| Method | Path | Auth | Handler → Service | Response |
|---|---|---|---|---|
| GET | `/contacts` | login required | `contacts.list_for_org(org, user=current_user)` + filters | HTML |
| GET | `/contacts/new` | login required | render form | HTML |
| POST | `/contacts/new` | login required | `contacts.create(...)` | redirect to detail |
| GET | `/contacts/<id>` | login required | `contacts.get_for_user(id, user)` | HTML or 404 |
| GET | `/contacts/<id>/edit` | login required | `contacts.get_for_user(id, user)` | HTML |
| POST | `/contacts/<id>/edit` | login required | `contacts.update(...)` | redirect |
| POST | `/contacts/<id>/delete` | login required | `contacts.delete(id, user)` | redirect to list |
| GET | `/contacts/import` | login required | render import form | HTML |
| POST | `/contacts/import` | login required | `contacts.import_csv(org, file_stream, ...)` | redirect to import report |
| GET | `/contacts/imports/<id>` | login required | `contacts.get_import(id, user)` | HTML — import report |
| GET | `/contacts/imports/<id>/errors.csv` | login required | `contacts.export_import_errors(id, user)` | CSV file download |
| POST | `/contacts/<id>/optout` | login required | `contacts.opt_out(id, user)` → `propagate_opt_out(phone)` | redirect |

**Form fields for create/edit** — `[VERIFY from handler
app/routes/contacts.py:create, update — expected name, phone, group_id,
district_id, notes]`.

**Duplicate phone handling.** The service rejects a duplicate phone
within the same org; the route flashes the error and re-renders the
form. Duplicates *across* orgs are allowed.

## 6a.6 `groups` — `/groups`

| Method | Path | Auth | Handler → Service | Response |
|---|---|---|---|---|
| GET | `/groups` | login required | `groups.list_for_org(org, user=current_user)` | HTML |
| GET | `/groups/new` | login required | render form | HTML |
| POST | `/groups/new` | login required | `groups.create(org, name, desc, user=current_user)` | redirect to detail |
| GET | `/groups/<id>` | login required | `groups.get_for_user(id, user)` | HTML or 404 |
| GET | `/groups/<id>/edit` | login required | `groups.get_for_user(id, user)` | HTML |
| POST | `/groups/<id>/edit` | login required | `groups.update(id, ...)` | redirect |
| POST | `/groups/<id>/delete` | login required | `groups.delete(id, user)` | redirect to list |

**Form fields** — `[VERIFY from handler
app/routes/groups.py:new — expected name, description]`. Department is
set from `current_user.department`, never from the form.

**Delete guard.** Hard delete. Contacts are not deleted — their
`group_id` is cleared. If a schedule references the group, the delete
proceeds and leaves an orphaned `group_id` (backlog #38).

## 6a.7 `campaigns` — `/campaigns`

Send-now and schedule routes share this blueprint.

| Method | Path | Auth | Handler → Service | Response |
|---|---|---|---|---|
| GET | `/campaigns` | login required | `campaigns.list_for_org(org, user=current_user)` | HTML |
| GET | `/campaigns/new` | login required | render form (three modes) | HTML |
| POST | `/campaigns/new` | login required | `campaigns.create_campaign(org, ..., user=current_user)` | redirect to detail |
| GET | `/campaigns/<id>` | login required | `campaigns.get_for_user(id, user)` | HTML or 404 |
| POST | `/campaigns/<id>/cancel` | login required | `campaigns.cancel(id, user)` | redirect |
| POST | `/campaigns/personalized/preview` | login required | `personalization.preview(org, body, csv_stream)` | JSON — per-row render preview |
| GET | `/campaigns/schedules` | login required | `schedules.list_for_org(org, user=current_user)` | HTML |
| GET | `/campaigns/schedules/new` | login required | render form | HTML |
| POST | `/campaigns/schedules/new` | login required | `schedules.create_schedule(org, ..., user=current_user)` | redirect to schedule detail |
| GET | `/campaigns/schedules/<id>` | login required | `schedules.get_for_user(id, user)` | HTML or 404 |
| GET | `/campaigns/schedules/<id>/edit` | login required | `schedules.get_for_user(id, user)` | HTML |
| POST | `/campaigns/schedules/<id>/edit` | login required | `schedules.update_schedule(...)` | redirect |
| POST | `/campaigns/schedules/<id>/delete` | login required | `schedules.delete_schedule(...)` | redirect to list |
| POST | `/campaigns/schedules/<id>/pause` | login required | `schedules.pause(...)` | redirect |
| POST | `/campaigns/schedules/<id>/resume` | login required | `schedules.resume(...)` | redirect |
| POST | `/campaigns/schedules/<id>/cancel` | login required | `schedules.cancel_schedule(...)` | redirect |

**Form fields for send-now** — `[VERIFY from handler
app/routes/campaigns.py:new — expected mode, body, target (group/district/all), group_id, district_id, personalized CSV upload, pasted numbers]`.

**Form fields for schedule** — `[VERIFY from handler
app/routes/campaigns.py:schedule_new — expected body, group_id, district_id,
days_of_week, times (multi), start_date, end_date]`.

**Suspend guard on `/campaigns/new`.** If `current_user.status !=
'active'`, the route flashes an error and redirects. Suspended users
can view but not initiate sends (see `02-architecture.md` §2.4).

**Send-now flow (per `02-architecture.md` §2.5)** — the route handler
is thin. All sequencing happens in `campaigns.create_campaign`, which
commits `Campaign` + wallet debit + `MessageLog` rows + `SendQueue`
entry as one transaction. If anything fails, rollback reverses all of
it — no orphan Campaign, no phantom debit.

## 6a.8 `chat` — `/chat`

| Method | Path | Auth | Handler → Service | Response |
|---|---|---|---|---|
| GET | `/chat` | login required | `chat.list_channels(user)` | HTML |
| GET | `/chat/<channel_id>` | login required | `chat.get_channel(channel_id, user)` | HTML |
| POST | `/chat/<channel_id>/send` | login required | `chat.send(channel_id, body, sender=user)` | redirect or JSON |
| GET | `/chat/<channel_id>/messages` | login required | `chat.list_messages(channel_id, since=ts, user)` | JSON — poll target |

The 3-second poll hits `GET /chat/<channel_id>/messages?since=<ts>`.
The response is `[VERIFY: exact JSON shape — expected {"messages":
[{id, sender, body, sent_at, is_read}], "last_ts": <ts>}]`. Read
state is tracked in `ChatReadState`.

## 6a.9 `billing` — `/billing`

| Method | Path | Auth | Handler → Service | Response |
|---|---|---|---|---|
| GET | `/billing/wallet` | login required | `wallet.get_balance(org)` + transactions | HTML |
| GET | `/billing/invoices` | login required | `billing.list_for_org(org)` | HTML |
| GET | `/billing/invoices/<id>` | login required | `billing.get_for_org(id, org)` | HTML |
| GET | `/billing/invoices/<id>/pdf` | login required | `invoice_pdf.render(invoice)` | PDF file download |

**Self-service plan purchase does not exist** — `/billing/plans/*`
routes are absent. Backlog #43. See `DEPARTMENTS.md` §2 for the model
and the trigger to change it.

## 6a.10 `reports` — `/reports`

| Method | Path | Auth | Handler → Service | Response |
|---|---|---|---|---|
| GET | `/reports` | login required | `reports.summarize(org, filters)` | HTML |
| GET | `/reports/delivery` | login required | delivery stats for a date range | HTML — `[VERIFY: exact route path and query params]` |
| GET | `/reports/export.csv` | login required | CSV export of usage | CSV download — `[VERIFY: exact route path]` |

The reports blueprint queries `MessageLog` filtered by status and date
range. It is org-scoped. The exact set of reports and their filters
should be verified against `app/routes/reports.py` before quoting
metric names — the guide above is structural.

## 6a.11 `profile` — `/profile`

| Method | Path | Auth | Handler → Service | Response |
|---|---|---|---|---|
| GET | `/profile` | login required | render profile page | HTML |
| POST | `/profile/password` | login required | `users.change_password(user, old, new)` | redirect with flash |

The department field on `/profile` is **read-only**. Users cannot
change their own department — the school admin does it from
`/school/users/<id>/edit`. This is a security invariant (see
`05-user-guide-school.md` §5.15).

## 6a.12 `school` — `/school`

**Auth: `@org_admin_required` and `department IS NULL`.** Every handler
in this blueprint checks that `current_user.role == 'associate_admin'`
and `current_user.department is None`. Dept-scoped admins and
`associate_user` roles get 404 or redirect.

| Method | Path | Handler → Service | Response |
|---|---|---|---|
| GET | `/school/users` | `orgs.list_users(org)` | HTML |
| GET | `/school/users/new` | render form | HTML |
| POST | `/school/users/new` | `orgs.create_school_user(org, ..., role, department)` | redirect to detail |
| GET | `/school/users/<id>` | `orgs.get_user_activity(id, org)` | HTML — detail page |
| GET | `/school/users/<id>/edit` | render form | HTML |
| POST | `/school/users/<id>/edit` | `orgs.update_school_user(...)` | redirect |
| POST | `/school/users/<id>/suspend` | `orgs.suspend_user(id, actor=current_user)` | redirect |
| POST | `/school/users/<id>/terminate` | `orgs.terminate_user(id, actor=current_user)` | redirect |
| POST | `/school/users/<id>/reactivate` | `orgs.reactivate_user(id, actor=current_user)` | redirect |
| POST | `/school/users/<id>/delete` | `orgs.delete_user(id, actor=current_user)` | redirect |
| POST | `/school/users/<id>/reset-password` | `users.reset_password(id)` | redirect |

**Form fields for create/edit** — `[VERIFY from handler
app/routes/school.py:user_new, user_edit — expected email, name,
password, role, department]`.

**Guards.** Service-level, in `orgs.py`:
- Cannot suspend/terminate/delete self
- Cannot suspend/terminate/delete last active `associate_admin` in org
- `associate_admin` requires `department=None` (rejected at creation
  time if the form submits a dept-scoped admin)

See `05-user-guide-school.md` §5.8 for the user-facing semantics.

## 6a.13 `settings` — `/settings`

**Auth: login required. Pool-sharing section requires
`department=None`.**

| Method | Path | Handler → Service | Response |
|---|---|---|---|
| GET | `/settings` | render settings page | HTML |
| POST | `/settings/org` | `orgs.update_settings(org, ...)` | redirect |
| POST | `/settings/pool/grant` | `pool.grant_permission(org, agreement_text, actor)` | redirect |
| POST | `/settings/pool/revoke` | `pool.revoke_permission(org)` | redirect |

**Form fields for org settings** — `[VERIFY from handler
app/routes/settings.py:org — expected name, contact_email, phone,
address]`. Org name/slug edits require `_refuse_if_protected` guard
for master/system orgs, but associates cannot reach those orgs
anyway.

**Pool agreement text** — the verbatim text stored on
`PoolPermission.agreement_text`. If the agreement wording changes, the
old permissions retain their old text — a legal record of what was
accepted. The current text lives in `[VERIFY: source — likely
app/services/pool.py or a constant]`.

## 6a.14 `notifications` — `/notifications`

| Method | Path | Auth | Handler → Service | Response |
|---|---|---|---|---|
| GET | `/notifications` | login required | `notifications.compute(org, user)` | HTML — live, not stored |
| POST | `/notifications/<key>/dismiss` | login required | `notifications.dismiss(user, key)` | redirect |

**Notification keys** are stable strings (e.g. `low_balance`,
`plan_expiring`, `no_contacts`). `NotificationDismissal` records
`(user_id, key, dismissed_at)`. When the underlying condition clears,
the dismissal row is garbage-collected or ignored — the notification
is live, so if the condition recurs, a fresh `key` is generated.
[VERIFY: exact key generation — does the key include a timestamp or
condition value, or is it a stable string? See
`app/services/notifications.py`.]

## 6a.15 `public` — `/` (unauthenticated)

| Method | Path | Auth | Handler → Service | Response |
|---|---|---|---|---|
| GET | `/optout` | none | render opt-out form | HTML — `[VERIFY: exact path — could be /opt-out or /optout]` |
| POST | `/optout` | none | `optout_links.opt_out(phone)` → `propagate_opt_out(phone)` | redirect to confirmation |
| GET | `/unsubscribe/<token>` | none | `optout_links.consume(token)` | HTML — one-click opt-out from SMS link |

**CSRF + rate limiting.** The POST endpoints are CSRF-protected and
rate-limited (per `PERMISSIONS.md`). The rate-limit parameters live in
`SIGNUP_*` config in `config.py` — `[VERIFY: exact config keys and
defaults]`.

**Opt-out propagation.** Every opt-out path — public form, one-click
link, manual contact opt-out, import with `opted_out=1` — calls
`propagate_opt_out(phone)` which touches `OptOut` and `PoolContact`.
This is non-negotiable: a phone that opts out is removed from every
list everywhere.

## 6a.16 `signup` — `/signup`

**Auth: none. CSRF-protected. Rate-limited.**

| Method | Path | Handler → Service | Response |
|---|---|---|---|
| GET | `/signup` | render signup form | HTML |
| POST | `/signup` | `signups.submit_request(...)` | redirect to acknowledgement |

**Form fields** — `[VERIFY from handler app/routes/signup.py:new —
expected org_name, slug, contact_name, email, phone, address,
vertical (optional)]`.

**Design constraint.** Public signup **never creates an Organization
directly**. It creates only a `SignupRequest`. The org is created at
master approval time, atomically with the initial admin user and the
starter credit transfer. This is a security invariant — no
unauthenticated path can create an org.

See `04-user-guide-master.md` §4.4 for the approval flow.

## 6a.17 `templates` — `/templates`

| Method | Path | Auth | Handler → Service | Response |
|---|---|---|---|---|
| GET | `/templates` | login required | `templates_svc.list_templates(org, user=current_user)` | HTML |
| GET | `/templates/new` | login required | render form | HTML |
| POST | `/templates/new` | login required | `templates_svc.create_template(org, ..., user=current_user)` | redirect |
| GET | `/templates/<id>` | login required | `templates_svc.get_for_user(id, user)` | HTML or 404 |
| GET | `/templates/<id>/edit` | login required | `templates_svc.get_for_user(id, user)` | HTML |
| POST | `/templates/<id>/edit` | login required | `templates_svc.update_template(...)` | redirect |
| POST | `/templates/<id>/delete` | login required | `templates_svc.delete_template(...)` | redirect |

**Form fields** — `[VERIFY: expected name, body]`. Department set from
`current_user.department`, never from the form.

**Route module name collision.** `app/routes/templates.py` (the route)
and `app/services/templates_svc.py` (the service, note the `_svc`
suffix) and `app/templates/` (the Jinja directory) are three different
things with "templates" in their names. Never rename the `_svc`
service; the shadow problem is why it has the suffix.

## 6a.18 `landing` — `/`

| Method | Path | Auth | Handler → Service | Response |
|---|---|---|---|---|
| GET | `/` | none | render landing page | HTML |

Marketing page. Links to `/signup`, `/auth/login`, `/optout`. No
authenticated content.

## 6a.19 `webhooks` — `/api/webhooks`

**Auth: token in URL path.** Not session-authenticated, not
CSRF-protected (external caller is Pahappa, not a browser form).

| Method | Path | Auth | Handler → Service | Response |
|---|---|---|---|---|
| POST | `/api/webhooks/transaction-status/<TOKEN>` | URL token | `webhooks.handle_transaction_status(...)` | JSON `{"ok": true}` |

The token is set in config as `EGOSMS_WEBHOOK_TOKEN` (or similar).
Pahappa posts delivery status reports here. Each report flips
`MessageLog.status` to `delivered` or `delivery_failed`. See
`02-architecture.md` §2.5 for the flow.

**Idempotency.** The webhook must be idempotent — Pahappa may retry.
Handlers check the current status and skip if already updated. This
is a correctness requirement, not an optimization.

## 6a.20 `master` — `/master`

**Auth: `@master_required` on every route.** Largest blueprint, 25+
handlers. Cross-org access is granted only here.

### Dashboard and orgs

| Method | Path | Handler → Service | Response |
|---|---|---|---|
| GET | `/master` | `master.dashboard()` — totals, recent activity | HTML |
| GET | `/master/orgs` | `master.orgs_index()` — all orgs | HTML |
| GET | `/master/orgs/new` | render form | HTML |
| POST | `/master/orgs/new` | `orgs.create_associate(...)` | redirect |
| GET | `/master/orgs/<id>` | `orgs.get_detail(id)` — users, wallet, subs | HTML |
| GET | `/master/orgs/<id>/edit` | render form | HTML |
| POST | `/master/orgs/<id>/edit` | `orgs.update_associate(...)` — guard `_refuse_if_protected` | redirect |

### Signups

| Method | Path | Handler → Service | Response |
|---|---|---|---|
| GET | `/master/signups` | `signups.list_requests(status=pending)` | HTML |
| GET | `/master/signups/<id>` | `signups.get(id)` — full detail | HTML |
| POST | `/master/signups/<id>/approve` | `signups.approve(req, actor, starter_credits, vertical)` | redirect |
| POST | `/master/signups/<id>/reject` | `signups.reject(req, actor, reason)` | redirect |

### Wallet and credits

| Method | Path | Handler → Service | Response |
|---|---|---|---|
| GET | `/master/orgs/<id>/grant` | render grant form | HTML |
| POST | `/master/orgs/<id>/grant` | `wallet.credit(org.id, amount, source_org_id=master_org.id, reason)` | redirect |

**Form fields for grant** — `[VERIFY: expected amount, reason
(dropdown from EXTERNAL_CREDIT_REASONS), notes]`.

### Plans

| Method | Path | Handler → Service | Response |
|---|---|---|---|
| GET | `/master/plans` | `plans.list_all()` | HTML |
| GET | `/master/plans/new` | render form | HTML |
| POST | `/master/plans/new` | `plans.create(...)` | redirect |
| GET | `/master/plans/<id>/edit` | render form | HTML — `[VERIFY: does edit exist or are plans immutable?]` |
| POST | `/master/plans/<id>/edit` | `plans.update(...)` | redirect |

### Invoices

| Method | Path | Handler → Service | Response |
|---|---|---|---|
| GET | `/master/invoices` | `billing.list_all()` | HTML |
| GET | `/master/orgs/<id>/new_invoice` | render invoice form | HTML |
| POST | `/master/orgs/<id>/new_invoice` | `billing.create_invoice(org, plan, actor)` | redirect |
| POST | `/master/invoices/<id>/mark-paid` | `billing.mark_paid(invoice, actor)` | redirect |
| GET | `/master/invoices/<id>/pdf` | `invoice_pdf.render(invoice)` | PDF download |

### Pool

| Method | Path | Handler → Service | Response |
|---|---|---|---|
| GET | `/master/pool` | `pool.list_pool_groups(filters)` | HTML |
| POST | `/master/pool/send` | `campaigns.create_pool_campaign(...)` — from system org | redirect |
| GET | `/master/pool/filters` | `pool.get_filter_options()` | JSON or HTML — `[VERIFY: exact route]` |

### Audit

| Method | Path | Handler → Service | Response |
|---|---|---|---|
| GET | `/master/audit` | `audit.list_all(filters)` | HTML |

### User password reset

| Method | Path | Handler → Service | Response |
|---|---|---|---|
| POST | `/master/orgs/<id>/users/<uid>/reset-password` | `users.reset_password(uid, actor=master)` | redirect |

**Master does not create school users** — see §4.5 and the Q1
answer in `DEPARTMENTS.md`.

## 6a.21 Error handlers

`app/errors.py` registers handlers for 400, 403, 404, 500, plus a
catch-all for CSRF failures. Handlers respect `request.accept_mimetypes`:
HTML requests get rendered error pages (`templates/errors/`), JSON
requests (mobile API or AJAX) get JSON error bodies.

**Cross-department 404 (not 403).** When a user requests a record
outside their department scope, the service `get_for_user` returns
`None` and the route turns it into 404, not 403. This avoids leaking
the existence of records the user is not allowed to see.

## 6a.22 Logging and request IDs

Every request logs with an `X-Request-ID` header. Nginx proxies the
header through to Flask. `app/logging_config.py` configures text logs
in dev, JSON logs in prod. Log lines from the worker carry no request
ID (no request context) — see `02-architecture.md` §2.16.

## 6a.23 How to add a new route (checklist)

1. New handler in the appropriate blueprint module.
2. Apply the correct decorator: `@login_required` at minimum,
   `@master_required` for cross-org, `@org_admin_required` for
   org-admin-only.
3. Pass `user=current_user` to any service that filters by department.
   Never accept `department` from the form.
4. If it accesses a record by ID, use `get_for_user(...)` and turn
   `None` into 404.
5. If it mutates wallet state, call the service — never mutate
   `WalletTransaction` directly.
6. Add a template in `app/templates/<blueprint>/`.
7. Add a test in `tests/integration/` — route-level, with
   `test_client()`.
8. If the route path is `/master/*`, confirm the permission matrix
   in `docs/PERMISSIONS.md` covers it and update the matrix if not.

---

*Part 6a of 10. See `07-api-mobile.md` next.*