# Changelog
# Changelog

## [0.9.0] — PDF invoices, completion emails, dashboard charts

### Added
- **Invoice PDF export** for associates and master. Download from the
  invoice detail page. Renders company details, line item, total, and
  payment instructions from config. Company details are configurable
  via `COMPANY_NAME`, `COMPANY_ADDRESS`, `COMPANY_PHONE`,
  `COMPANY_EMAIL`, `COMPANY_TIN`.
- **Campaign completion emails.** When a campaign finishes sending,
  the creator and all associate admins get a summary email. Gated by
  `EMAIL_ON_CAMPAIGN_COMPLETE=1`.
- **Dashboard usage charts.** Replaced the placeholder stats with a
  wallet hero card, delivery donut, 30-day send trend, and credit
  burn rate indicator. All rendered server-side — no JS dependencies.

### Changed
- `sent_30d` on the dashboard now counts messages that reached the
  network (`sent` + `delivered` + `delivery_failed`), not just those
  still awaiting webhook confirmation. The delivery rate is now
  computed against a coherent population.
- Context processors (`_inject_notifications`, `_inject_wallet`) guard
  against background jobs. Services can now render templates from the
  worker or cron context without crashing.

### Fixed
- Delivery rate was previously `delivered / (still-pending)`, which
  produced nonsense ratios once the webhook ran.
- `services/pool.unique_recipients` was defined twice; the second
  definition silently dropped the `group_name` parameter, breaking
  pool sends filtered by group.
- `routes/signup.py` redirected to a nonexistent `auth.root` endpoint
  for authenticated users.
- `routes/webhooks.py` `_parse_iso8601` stored server-local time in
  `MessageLog.delivered_at` instead of UTC.
- Welcome email said "expires in 24 hours" but the token expired in 1.
  Reset and welcome tokens now carry separate lifetimes.
- `Campaign.sender_id` and `CampaignSchedule.sender_id` were
  `String(11)`; populated from `brand_name` which is `String(60)`.
  Postgres rejected any brand name longer than 11 characters.
- `routes/campaigns.py` never read `recipient_source` /
  `pasted_numbers` from the form, so the paste feature shipped in
  0.8.1 was unreachable from the UI.
- `routes/campaigns.py` `detail()` never passed `breakdown` to the
  template.
- `routes/master.py` `org_detail()` never passed `balance_ugx` /
  `rate_ugx` after the 0.7.2 shilling-display change.
- `create_associate` didn't cap `brand_name` at 20 characters, unlike
  `update_associate`.
  
## [0.8.1] — Campaign form polish
### Added
- **Character / segment / cost counter** on the new campaign form.
  Live updates as the associate types. Counts the **brand prefix plus
  the message body**, not just the body, so the segment count matches
  what actually leaves the platform and what Pahappa bills for.
  Display: `N chars · M SMS · UGX X`.
- **"Paste numbers" recipient source** on the campaign form. Associates
  can send to a one-off list of phone numbers without adding them to
  the contact database. Numbers are parsed with the same rules as CSV
  import (Ugandan mobile only), deduplicated, and checked against the
  platform-wide opt-out list. Capped at 500 per campaign.

### Changed
- **Schedule fields are always visible** on the campaign form, dimmed
  when "Send now" is selected rather than hidden. The scheduling
  feature is now discoverable without clicking through options first.

### Why
- An associate typing a message had no visibility into whether they
  were about to be charged for one SMS or three. The cost difference is
  real money and the trigger — crossing 160 characters — is invisible
  without a counter.
- EgoSMS's own form counts raw characters, ignoring the brand prefix.
  That is wrong for a reseller: the associate pays for the prefix too,
  so the counter must reflect the full delivered message.
- The paste-numbers feature matches a common EgoSMS pattern and closes
  a gap for one-off sends to people who are not worth adding to the
  contact list.

### Verified
- Typing a 150-character body with a 13-character prefix shows 163
  characters and 2 SMS, with the doubled cost reflected.
- Pasting a list of 10 numbers with 2 duplicates and 1 invalid shows
  7 eligible recipients in the count before submitting.
- Switching between "From my contacts" and "Paste numbers" preserves
  the other field's value so the associate can flip back without
  re-entering data.

## [0.8.0] — Recurring campaigns
### Added
- **`CampaignSchedule`** — a rule for recurring sends. Stores days of
  the week (`mon`..`sun`), times of day (JSON `["09:00","14:00"]`),
  start and end dates, and the group/district filters.
- **`services/schedules.py`** — `create_schedule`, `pause_schedule`,
  `resume_schedule`, `cancel_schedule`, `claim_due_schedule`,
  `materialize_run`. Recipients are resolved fresh at every run; the
  wallet is debited per run; failure to debit (empty wallet) pauses
  the schedule with a clear reason.
- **Worker scheduler pass.** `worker.py` now runs
  `run_scheduler_pass()` before the send queue drain on every tick.
- **Routes** — `/campaigns/schedules`, `/campaigns/schedules/<id>`,
  and `pause`/`resume`/`cancel` actions.
- **Templates** — schedules list, schedule detail with run history.
- **New campaign form** now has "Send now" / "Schedule" radio buttons.
  Selecting Schedule reveals day checkboxes, time picker, and active
  window.
- **Config** — `SCHEDULER_TZ_OFFSET_HOURS` (default 3 for EAT).

### Changed
- `Campaign` gains `schedule_id` foreign key. Null for directly-queued
  campaigns, set for campaigns materialized from a schedule.

### Why
- Recurring sending is the number one associate request. Fee
  reminders, weekly promotions, and monthly statements are all
  patterns that need a rule, not a single send.
- Separate entity keeps the mental model clean: a Campaign has one
  recipient list and one debit; a Schedule is a rule that produces
  many of each over time.

## [0.7.2] — Balances displayed in shillings
### Changed
- **Every balance in the UI now shows as UGX**, with the SMS count as
  secondary text. Top-bar pill, wallet page, dashboard, master org
  detail, master org list.
- **Wallet transactions** show the shilling change with the SMS count
  as a smaller subtext under each row.
- **Master grant form** labels the amount as "SMS credits" and shows
  the shilling equivalent for the associate.

### Added
- `services/entitlements.current_rate_ugx(org_id)` — returns the
  effective UGX value of one credit based on the org's active plan.
  Falls back to UGX 50 when no plan is active.
- `services/entitlements.balance_value_ugx(org_id)` — convenience.
- Context processor now injects `wallet_balance`, `wallet_rate`, and
  `wallet_value_ugx` into every authenticated template.

### Why
- Associates think in money. The internal ledger still tracks integer
  credits for arithmetic correctness, but the display layer shows the
  shilling value so the associate always knows what they have paid for
  and what is left.

## [0.7.1] — Price increase + real-cash UI
### Changed
- **Retail prices raised by UGX 5 per SMS on every tier.** Starter 45→50,
  Growth 40→45, Business 35→40, Scale 30→35. Existing invoices
  unaffected (snapshot at creation). Applied via
  `scripts/update_prices_2026_10.py`.
- **Wallet display now shows SMS count and UGX value side by side.**
  Associates see "3,200 SMS worth approximately UGX 144,000" instead of
  a bare integer.
- **Top-bar wallet pill label** changed from "credits" to "SMS".
- **Plans page** shows savings per SMS vs Starter tier on each row.

### Added
- **Master margin card** on the org detail page. Shows UGX billed vs
  UGX wholesale cost for the last 30 days, plus net margin. Red when
  the associate is underwater, amber below UGX 50,000 margin, green
  above.

### Why
- The API charges vary by network and volume. Two consecutive test
  sends came back at 35 and 20 UGX. Retail was priced at a flat UGX 35
  assumption, which cannot hold under that variance.
- A 5 UGX buffer per SMS covers the worst case with a positive margin
  on every tier.

## [0.7.0] — Signups, import reporting, pool groups
### Added
- **Gated self-signup.** Public form at `/signup`. Applicant submits;
  master reviews at `/master/signups`; approval creates the org, admin
  user, and starter credit grant in one transaction. Welcome email
  contains a password-setup link. `SIGNUP_ENABLED=0` disables the route
  without a deploy. `SignupRequest` model with full agreement / IP /
  user-agent capture.
- **Contact import reporting.** Every import creates a `ContactImport`
  job and one `ContactImportIssue` per skipped row. Report page at
  `/contacts/imports/<id>` with counts, filter tabs by status, and a
  downloadable CSV of skipped rows suitable for fixing and re-uploading.
  History at `/contacts/imports`.
- **Pool group filter.** `PoolContact.group_name` snapshotted at
  contribution time. Group filter dropdown on both the pool list and the
  pool send form. Group column shows as a clickable pill that filters the
  list. "Contributions by group" breakdown table on the pool page.
- **Stricter phone normalization.** `services/phones.py` now rejects
  landlines and any number that does not reduce to `2567XXXXXXXX`.
  `describe()` returns a reason string for the import preview.
- **Nullable name and district on contacts.** `add_contact` and
  `update_contact` store `None` for empty strings so the display layer
  can distinguish "no name" from "empty name".
- **`flask seed-all`** command. Runs both seed scripts in order.
- **`flask info`** command. Prints environment counts and configuration.
- **`scripts/backfill_pool_groups.py`** for one-time backfill of
  existing pool contacts.
- **`scripts/test_wallet_concurrency.py`** verifies the FOR UPDATE lock
  actually serialises under Postgres.
- **`docker-compose.yml`** for local Postgres.

### Changed
- **Database backend is Postgres.** Config raises at import time if
  `DATABASE_URL` is missing — no silent SQLite fallback that would break
  the wallet. `psycopg[binary]` is the driver.
- **`services/contacts.import_csv`** returns a `ContactImport` job, not
  a dict. Routes redirect to the report page instead of flashing a
  summary.
- **`services/pool.unique_recipients`** accepts a `group_name` filter.
- **`services/pool.pool_stats`** returns `by_group` in addition to
  `by_district_id` and `by_source`.
- **`services/pool._copy_contacts_into_pool`** snapshots the group name
  from the source contact.
- **`base.html`** redesigned with collapsible sidebar, cleaner top bar,
  breadcrumb, command-palette search hint, and refreshed dropdown
  animations.
- **`.env.example`** gains `SIGNUP_ENABLED`, `SIGNUP_STARTER_CREDITS`,
  `WEBHOOK_TOKEN`.

### Fixed
- Audit route silently shadowed the `audit()` helper. Route handler
  renamed to `audit_view`; endpoint is now `master.audit_view`.
- `NoReferencedTableError` for `district` — `app/models/__init__.py`
  imports `District` first and calls `configure_mappers()` to fail loudly
  on any future import-order mistake.
- Sidebar active-state check was firing on every sibling link. Now keyed
  on URL path, not endpoint prefix.
- Missing `OptOut` import in `routes/contacts.py`.
- Missing `psycopg` driver when SQLAlchemy 2.0 targets a Postgres DSN.

### Verified
- Webhook receiver: curl with valid token returns `{"matched": 1,
  "ok": true}` and updates the row.
- Wallet concurrency test passes on Postgres (one debit succeeds, one is
  refused, invariant holds).
- `seed_districts.py` completes with all four regions populated.
- Contact import handles BOM, mixed-case headers, and every duplicate
  category correctly.

### Notes
- Phase 5 (registered sender IDs) remains gated on a paying client.
- Awaiting Pahappa production credentials. `EGOSMS_SANDBOX=1` remains in
  `.env` until they arrive.

## [0.6.0] — Post-Phase-4 polish: districts, pool, chat, webhook
### Added
- **Districts.** Reference table with all ~135 Ugandan districts grouped
  by region. `Contact.district_id` and `Organization.district_id`.
  District filter on contacts, import, and campaign creation.
  `scripts/seed_districts.py` is idempotent.
- **Master pool.** `PoolPermission` (with agreement text snapshot and
  version) and `PoolContact` (one row per source_org + phone). Associates
  grant/revoke from `/settings`. Master views at `/master/pool` with
  filters and contributions breakdown. Pool campaigns send from the
  system org. `propagate_opt_out` fires from every opt-out entry point.
- **System org.** `Organization.is_system`. "Roman SMS Platform" (slug
  `roman-platform`) is the sending identity for pool campaigns. Master
  org keeps operating funds only. Master sidebar gains a Platform sender
  page with balance, top-up, ledger, and campaigns.
- **In-app chat.** DM (master ↔ one associate) and broadcast channels.
  3-second polling, read state per user per channel. Sidebar badge on
  unread. Channel list with previews.
- **Notifications.** Computed from live conditions each render. Types
  (success / danger / warning / info) with icons. Bell dropdown in the
  top bar with per-item dismiss (X) and a "View all" page at
  `/notifications` with filter tabs. `NotificationDismissal` records
  what a user has hidden. Badge updates live after dismissal.
- **Profile and Settings.** `/profile` for name, email, password.
  `/settings` for the pool permission grant and revocation.
- **Webhook for delivery status.** `/api/webhooks/transaction-status/<token>`
  receives POSTs from Pahappa. Matches on `MsgFollowUpUniqueCode` +
  `number`. Updates `MessageLog.status` to `delivered` or
  `delivery_failed`, stores `delivered_at` and `delivery_status_raw`.
  Token in URL, mismatch returns 404.
- **Admin CLI commands.** `flask egosms-balance`, `flask egosms-test`,
  `flask fund-master`, `flask fund-platform`, `flask reconcile`,
  `flask expire-subs`, `flask seed`.
- **EgoSMS client rewrite.** Correct response parsing for the live API
  (`Status`, `Cost`, `MsgFollowUpUniqueCode`). Batch cap of 1000 enforced.
  Sandbox endpoint toggle via `EGOSMS_SANDBOX`. Never raises on network
  error; returns an `EgoSMSResponse` so the worker can refund cleanly.
- **Balance query.** `EgoSMSClient.balance(wallet_type)` returning an
  `EgoSMSBalanceResponse`. Local / international wallet types per docs.

### Changed
- **`_apply_response` in dispatch** now reads the parsed `EgoSMSResponse`
  object instead of guessing from a raw dict. Failed batches (`ok=False`)
  now correctly mark every message failed and refund.
- **`MessageLog` gained** `provider_cost`, `delivery_status_raw`, and
  `delivered_at`.
- **`MessageLog.status`** now includes `delivered` and `delivery_failed`
  as terminal states reported by the webhook.
- **`base.html`** redesigned: dark collapsible sidebar, top bar with
  breadcrumb, global search, notifications dropdown, user menu.
- **`orgs.list_associates`** filters `is_system=False` so the system org
  never appears as a client.

## [0.5.0] — Phase 4: Hardening
### Added
- `services/ratelimit.py` — per-org minute and day counters read from
  MessageLog.
- Dispatch enforces rate limits.
- `services/optout_links.py` — signed one-click opt-out tokens.
- `services/mailer.py` — pluggable mail backend.
- `services/password_reset.py` — signed reset tokens.
- Public routes: `/opt-out`, `/forgot-password`, `/reset-password`.
- `app/logging_config.py` — text or JSON logging.
- Login rate limited to 10/min per IP.
- Every outbound message appends a one-click opt-out link.
- `scripts/reconcile.py` sends an alert email on drift.
- `scripts/backup.py` — SQLite and Postgres backup with rotation.

## [0.4.0] — Phase 3: Billing
### Added
- Invoice snapshot fields.
- `services/billing.py`.
- Associate and master billing routes.
- Billing templates.
- Tests for the billing flow.

## [0.3.1] — Phase 2 verification
### Added
- Group tests (unit + integration).
- `scripts/smoke.py`.

## [0.3.0] — Phase 2: Master console
### Added
- `services/orgs.py`, `services/plans.py`, `services/subscriptions.py`.
- Master routes and templates.
- Sidebar navigation for master.

## [0.2.0] — Phase 1: Core sending
### Added
- Core services: entitlements, contacts, templates, campaigns, egosms
  client, dispatch.
- `worker.py`.
- Contacts, templates, campaigns, reports routes and templates.
- `scripts/reconcile.py`.
- Deploy units.

## [0.1.0] — Phase 0: Foundation
### Added
- Flask app factory, extensions, error handlers.
- Full data model.
- Role decorators and `org_scoped()`.
- Auth routes.
- Master console (read-only).
- CLI commands.
- Seed script.
- Project scaffolding.