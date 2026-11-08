# System structure

A one-page map of where everything lives. Read this before grepping.

**Recon date:** 2026-11-08 (branch `wip/mobile-api` @ `a671430`).

## Repository layout

    D:\Dev_Apps\roman_sms\
      app/                 Flask application (all source)
      docs/                Every .md doc - NOT at repo root
      migrations/          Alembic - versions/ has the revision chain
      mobile/              Flutter client
      scripts/             One-off ops scripts
      tests/               pytest - unit/ + integration/ + fixtures/
      deploy/              systemd units, nginx, env example
      config.py            Env-driven config classes
      wsgi.py              WSGI entrypoint

**Working style gotcha:** the docs (`BACKLOG.md`, `SCOPE.md`, etc.) live in
`docs/`, not the repo root. A bare `BACKLOG.md` at root is a stray - never commit it.

## Layers (per ARCHITECTURE.md)

    routes / api / worker / cli  ->  services  ->  models  ->  Postgres
                                            \->  EgoSMS/Pahappa API

Routes are HTTP glue. Services hold every business rule. The worker and CLI
call the same services. Nothing enforces a rule twice.

## app/ - directory map

| Path | Contents | Notes |
|---|---|---|
| `app/__init__.py` | `create_app()` factory, blueprint registration, context processors | |
| `app/extensions.py` | `db`, `login_manager`, `csrf`, `migrate` singletons | |
| `app/errors.py` | Error handlers (HTML + JSON) | |
| `app/logging_config.py` | Text or JSON logging | |
| `app/permissions.py` | `master_required`, `org_admin_required`, `org_scoped` | |
| `app/cli.py` | Flask CLI commands - 16 registered in `register_cli(app)` | See CLI section |
| `app/models/` | 12 modules, 25 `db.Model` classes | |
| `app/services/` | 30 modules, every business rule | |
| `app/routes/` | 17 HTML blueprints | |
| `app/api/v1/` | 12 files, JSON API for Flutter | |
| `app/templates/` | Jinja2 templates (46 files) | |
| `app/static/` | CSS/JS | |

## Models - `app/models/`

| Module | Classes | Table |
|---|---|---|
| `organization.py` | `Organization`, `User(UserMixin, db.Model)`, `Plan`, `Subscription` | `organization`, `user`, `plan`, `subscription` |
| `messaging.py` | `Group`, `Contact`, `MessageTemplate`, `Campaign`, `MessageLog` | `contact_group`, `contact`, `message_template`, `campaign`, `message_log` |
| `ops.py` | `SendQueue`, `OptOut`, `AuditLog`, `NotificationDismissal` | `send_queue`, `opt_out`, `audit_log`, `notification_dismissal` |
| `wallet.py` | `WalletTransaction`, `Invoice` | `wallet_transaction`, `invoice` |
| `pool.py` | `PoolPermission`, `PoolContact` | `pool_permission`, `pool_contact` |
| `scheduling.py` | `CampaignSchedule` | `campaign_schedule` |
| `chat.py` | `ChatChannel`, `ChatMessage`, `ChatReadState` | `chat_channel`, `chat_message`, `chat_read_state` |
| `geo.py` | `District` | `district` |
| `imports.py` | `ContactImport`, `ContactImportIssue` | `contact_import`, `contact_import_issue` |
| `signup.py` | `SignupRequest` | `signup_request` |
| `api.py` | `ApiToken`, `ApiIdempotency` | `api_tokens`, `api_idempotency` |

**Note on `User`:** inherits `UserMixin` first, `db.Model` second
(`class User(UserMixin, db.Model)`). `current_user` is a `User` with Flask-Login
methods (`is_authenticated`, `get_id`, `role`, `org_id`). Any serializer or
service touching `current_user` should treat it as a `User`, not a raw row.

**Import order gotcha** (CHANGELOG 0.7.0): `app/models/__init__.py` imports
`District` first and calls `configure_mappers()` - this fails loudly on any
future import-order mistake.

## Services - `app/services/`

30 modules. Key ones by concern:

| Concern | Modules |
|---|---|
| **Wallet / money** | `wallet.py` (append-only ledger), `billing.py` (invoices), `entitlements.py` (rate, can_send, contact limits), `subscriptions.py`, `invoice_pdf.py` |
| **Messaging** | `campaigns.py`, `renderer.py` (`substitute`, `render`, `segments`), `dispatch.py` (worker job), `schedules.py`, `templates_svc.py` (note the `_svc` suffix - avoids `app/templates/` collision), `ratelimit.py` |
| **Contacts** | `contacts.py`, `groups.py`, `phones.py` (`normalize_ug`, `parse_pasted_numbers`) |
| **Orgs** | `orgs.py`, `plans.py`, `users.py`, `signups.py`, `pool.py` |
| **Ops** | `notifications.py`, `audit.py`, `chat.py`, `mailer.py`, `optout_links.py`, `password_reset.py`, `campaign_notifications.py`, `geo.py`, `pahappa_balance.py` |

**`templates_svc.py`, not `templates.py`** - the trailing `_svc` exists because
`app/templates/` would shadow an import named `templates`. Never rename it.

## Routes - `app/routes/` (17 HTML blueprints)

| Blueprint | URL prefix | Module |
|---|---|---|
| `auth` | `/auth` | `auth.py` |
| `dashboard` | `/dashboard` | `dashboard.py` |
| `contacts` | `/contacts` | `contacts.py` |
| `groups` | `/groups` | `groups.py` |
| `campaigns` | `/campaigns` | `campaigns.py` |
| `chat` | `/chat` | `chat.py` |
| `billing` | `/billing` | `billing.py` |
| `reports` | `/reports` | `reports.py` |
| `profile` | `/profile` | `profile.py` |
| `settings` | `/settings` | `settings.py` |
| `notifications` | `/notifications` | `notifications.py` |
| `public` | `/` (opt-out, reset) | `public.py` |
| `signup` | `/signup` | `signup.py` |
| `templates` | `/templates` | `templates.py` (route, no collision) |
| `landing` | `/` | `landing.py` |
| `webhooks` | `/api/webhooks` | `webhooks.py` |
| `master` | `/master` | `master.py` - largest, 25+ handlers |

## API v1 - `app/api/v1/` (12 files, JSON)

| Module | Routes |
|---|---|
| `auth.py` | login, logout, me, signup, update_profile, change_password |
| `dashboard.py` | index (`GET /api/v1/dashboard`) |
| `wallet.py` | summary, transactions |
| `plans.py` | index |
| `campaigns.py` | preview, index, detail, create |
| `contacts.py` | index, create, patch, delete, optout, get |
| `groups.py` | index, create, get, list_contacts, patch, delete |
| `chat.py` | channels, messages, send_message |
| `notifications.py` | index, dismiss |
| `serializers.py` | `iso`, `user`, `org`, `wallet`, `contact`, `campaign`, `group`, `paginated` |
| `utils.py` | `install_api_errors`, `install_api_auth`, `require_idempotency` |

**CSRF exemption** is per-child-blueprint, not on `api_v1_bp` alone - see
`app/api/v1/__init__.py` `_CHILDREN`. New child blueprints must be added there.

## Migrations - `migrations/versions/`

Three revisions, linear chain:

    5e5fea16ea4e (base)
    +-- 00404835aeb7
        +-- 6c7a338d1274 (head - Contact.group_id NOT NULL, ContactImport.skipped_no_group)

Check with `flask db current` before any deploy that touches models.

## Config - `config.py`

Env-driven, two classes (`Config`, `TestConfig`). Every value has a safe default
except `DATABASE_URL` (raises at import if missing - no SQLite fallback, per CHANGELOG 0.7.0).

Key groups: `EGOSMS_*` (Pahappa), `WORKER_*` (dispatch tuning), `MAIL_*` (SMTP),
`BACKUP_*`, `LOG_*`, `SIGNUP_*`, `SCHEDULER_TZ_OFFSET_HOURS`, `COMPANY_*`.

## CLI commands - `app/cli.py`

16 registered via `@app.cli.command('name')` inside `register_cli(app)`:

`seed-all`, `seed`, `seed-districts`, `grant`, `fund-master`, `fund-platform`,
`create-org`, `reset-password`, `bulk-send`, `egosms-balance`, `egosms-test`,
`reconcile`, `expire-subs`, `backup`, `info`.

New commands go inside `register_cli` with the same decorator shape.

## Templates - `app/templates/` (46 HTML files)

Grouped by route blueprint: `auth/`, `billing/`, `campaigns/`, `chat/`,
`contacts/`, `dashboard/`, `errors/`, `groups/`, `landing/`, `master/` (15 files -
largest), `notifications/`, `profile/`, `public/`, `reports/`, `settings/`,
`signup/`, `templates/`. Plus `base.html` (shell).

## Tests - `tests/`

`tests/unit/` (13 files) - service-level. `tests/integration/` (10 files) -
route-level with `test_client()`. `tests/fixtures/` - CSV fixtures.
`tests/factories.py` - model factories. `tests/conftest.py` - pytest setup.

**Mobile API has no test coverage** as of 0.12.0 (ADR-019). Promote
`test_mobile_api.py` before the next feature lands on `/api/v1/`.

## Mobile - `mobile/`

Flutter, Riverpod + go_router + Dio. `lib/screens/` = 17 screens. Base URL hardcoded
in `lib/api/client.dart` to `https://romansms.com` - must become `--dart-define`
before any staging deploy (ADR-022). `INTERNET` permission must be in
`android/app/src/main/AndroidManifest.xml` (release builds don't auto-inject).

## Scripts - `scripts/`

16 one-shot ops/seed/maintenance scripts. Not imported by the app.

## Where do I put a new...?

| Need | Location |
|---|---|
| New model | `app/models/<concern>.py`, import it in `app/models/__init__.py` in the right order (District first) |
| New service function | `app/services/<concern>.py` - a service call, not a route-inline rule |
| New HTML page | Route in `app/routes/<blueprint>.py`, template in `app/templates/<blueprint>/` |
| New API endpoint | `app/api/v1/<resource>.py`; serializer in `serializers.py`; must be CSRF-exempt via `_CHILDREN` if a new blueprint |
| New CLI command | `app/cli.py` - inside `register_cli` |
| New migration | `flask db migrate -m "..."` then review - never edit a live revision |
| New ADR | `docs/DECISIONS.md` |
| New backlog item | `docs/BACKLOG.md` Parking lot (single-line entry) + detail in "Ideas considered and parked" |

## Known stale / traps

- `BACKLOG.md` at repo root is a stray - the real one is `docs/BACKLOG.md`.
- `services/templates_svc.py` != `services/templates.py` - do not rename.
- `app/templates/` is a **directory**, `app/routes/templates.py` is a **route module**,
  and `services/templates_svc.py` is the **service**. Three different things.
- `PATCH /api/v1/contacts/<id>` etc. exist; but `PATCH /api/v1/campaigns/<id>` does not.
- Migration head on prod = `6c7a338d1274`. Verify with `flask db current` before trusting.