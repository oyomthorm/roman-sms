# Changelog
## [0.12.0] — Mobile API deployed; signup, wallet, plans fixes; Flutter client working

### Deployed
- **Mobile API v1 is live on production.** All 17 `/api/v1/*` routes were
  previously unreachable because `create_app()` raised
  `AttributeError: 'Flask' object has no attribute 'unauthorized_handler'`.
  This bug survived to production because the mobile API was written on
  a branch that had never booted. `89593c7` fixed it. The mobile API is
  now tested end-to-end against `https://romansms.com` with real users.
- **Flutter client deployed to a physical Android device.** Login,
  signup, wallet, plans, chat, notifications, and all navigation routes
  work against production.

### Fixed
- **Boot crash** (see Deployed above).
- **CSRF exemption** moved from a `csrf.protect` monkey-patch in
  `create_app()` to explicit per-child-blueprint `csrf.exempt()` calls in
  `app/api/v1/__init__.py`. The monkey-patch is gone.
- **Wildcard CORS** removed. No browser client exists; wildcard CORS on
  a Bearer-authenticated API was a hazard given a leaked token.
- **`entitlements.balance(oid)` → `entitlements.get_balance(oid)`** in
  `wallet.summary`. The old function never existed; `/api/v1/wallet`
  had been 500-ing on every request since it was written. The `or 0`
  fallback never caught the error because `AttributeError` is not `None`.
- **`/api/v1/campaigns` paste path** was broken at three levels:
  called nonexistent `resolve_pasted_numbers`, passed `synthetic_contacts=`
  to a function expecting `custom_phones=`, and did not unpack the
  `(campaign, total_segments)` tuple `create_campaign` returns. Fixed by
  mirroring the web route: `parse_pasted_numbers` → `create_campaign(custom_phones=...)`
  → unpack → serialize.
- **`serializers.campaign`** read `c.recipient_count` and `c.cost_credits`
  via `getattr(..., 0)`; the Campaign model has `total` and `credits_debited`.
  Every campaign ever returned by the mobile API had zeros for both fields.
  Fixed to read real columns.
- **`/api/v1/plans`** read `p.price_ugx` / `p.rate_ugx`; Plan has `price`
  and derives `rate = price / credits`. 500'd on every request before this fix.
- **`/api/v1/chat/*`** cross-tenant leak: `channels()` had no org filter,
  `messages(cid)` and `send_message(cid)` had no ownership check. Fixed
  to scope by `associate_org_id`, with `ChatMessage.author_id` and
  `ChatReadState.last_read_at` (both of which were previously referenced
  under wrong names).
- **`chat.messages`** response field names updated to `author_id` /
  `created_at` (was `sender_id` / `sender_name`). Client impacts none
  because chat messages had never been reachable from any client.

### Added
- **`POST /api/v1/auth/signup`** — public signup endpoint that mirrors
  the web signup form. Anonymous (no token required), honeypot-aware
  (mobile always sends `website=""`, matching web behavior), rate-limited
  at 5/hour/IP. Returns 201 with `{ok, created, request_id, message}`.
  Does **not** issue a token; the applicant is notified after master
  approval via the existing welcome-email flow.

### Discovered, not fixed (deferred to 0.13.0+)
- **SMTP is unconfigured on production.** `MAIL_SERVER`, `MAIL_USERNAME`,
  `MAIL_PASSWORD`, `ALERT_EMAIL` are all empty or absent in
  `/srv/roman-sms/.env`. Signup applications land in `signup_requests`
  table but neither the applicant nor the master receives any email.
  **This is a documented, accepted deficiency** — signup is
  functionally complete, notification is not.
- **`POST /api/v1/invoices` and `GET /api/v1/invoices`** do not exist.
  The mobile Plans screen's "Buy Plan" button calls `/api/v1/invoices`
  and will 404. Purchase flow is web-only until these are added.
- **`GET /api/v1/campaigns/<id>`** does not exist. The mobile campaign
  detail screen will 404 when tapping a campaign in the list.
- **`GET /api/v1/dashboard`** does not exist. The mobile Dashboard
  screen uses `dashboardStatsProvider` which returns hardcoded
  `sent_30d: 12450, delivery_rate: '98.2%'` values.
- **`PATCH /api/v1/contacts/<id>`, `DELETE /api/v1/contacts/<id>`,
  `POST /api/v1/contacts/<id>/optout`** do not exist. Contact editing
  and opt-out are web-only.
- **Groups CRUD** endpoints do not exist. Contact groups are web-only.
- **`POST /api/v1/campaigns/schedules`** and related endpoints do not
  exist. Recurring campaign scheduling is web-only.
- **`PUT /api/v1/auth/profile`** and **`POST /api/v1/auth/change-password`**
  do not exist. The mobile Profile screen shows hardcoded
  "admin@example.com" / "Organization Admin" values.

### Notes
- The mobile API had never worked in production before 0.12.0. The
  pattern of latent bugs (wrong function names, wrong model field names,
  unpacked tuples) suggests the API was written against a mental model
  of the codebase, not against the actual code. See ADR-019.
- **Flutter APK build note**: `android/app/src/main/AndroidManifest.xml`
  must include `<uses-permission android:name="android.permission.INTERNET"/>`.
  Debug builds auto-inject this; release builds do not. Missing this
  permission produces "Connection Refused" on every network call and is
  a common source of confusion (the app works in `flutter run` but fails
  in `flutter build apk --release`).
- **Flutter base URL** is hardcoded to `https://romansms.com` in
  `mobile/lib/api/client.dart`. Change this before any deploy to a
  different environment; the value should eventually be moved to
  `--dart-define=API_BASE_URL=...`.
  
## [0.11.0] — Mobile API audit: C1/C2/C3 fixes, boot repair, CSRF refactor

### Fixed
- **Boot crash from `@app.unauthorized_handler`.** Flask has no such
  method; the correct API is `login_manager.unauthorized_handler`. The
  AttributeError occurred inside `create_app()`, so `api_v1_bp` was
  never registered on a booted app. Every `/api/v1/*` route was
  unreachable. This masked a deeper problem: the mobile API had never
  successfully booted.
- **`/api/v1/wallet` 500'd on every request.** The handler called
  `entitlements.balance(org_id)`, a function that does not exist. The
  real function is `entitlements.get_balance(org_id)`. The `or 0`
  fallback never fired because `AttributeError` is not `None`, so the
  bug was silent from day one.
- **`/api/v1/campaigns` paste path was broken at three levels.**
  (a) Called `camp_svc.resolve_pasted_numbers`, which does not exist.
  (b) Passed `synthetic_contacts=` to `create_campaign`, which expects
  `custom_phones=`. (c) Did not unpack the `(campaign, total_segments)`
  tuple that `create_campaign` returns. All three were masked because
  (a) raised first, so (b) and (c) never triggered. Fixed by mirroring
  the web route: `phones.parse_pasted_numbers` → `create_campaign(custom_phones=...)`
  → unpack → serialize.
- **`serializers.campaign` returned zeros for recipient_count and
  cost_credits.** The serializer read `c.recipient_count` and
  `c.cost_credits` via `getattr(..., 0)`, but the Campaign model has
  `total` and `credits_debited`. Fixed to use the real column names.
- **Chat cross-tenant leak in `/api/v1/chat/*`.** `channels()` listed
  every chat channel in the database with no org filter;
  `messages(cid)` and `send_message(cid)` never checked ownership. Any
  logged-in associate could read or post to another org's DM by
  iterating integer channel ids. Fixed: all channel access goes
  through `_channel_visible_or_404(cid)` which scopes by
  `associate_org_id` (dm) or `associate_org_id IS NULL or current_org`
  (broadcast). `ChatMessage.author_id` and `ChatReadState.last_read_at`
  corrected (previously used nonexistent `sender_id` / `last_read_message_id`).

### Changed
- **CSRF exemption moved from `create_app()` to `app/api/v1/__init__.py`.**
  Previously a monkey-patch on `csrf.protect` skipped CSRF for any path
  starting with `/api/`. Replaced with `csrf.exempt(child_bp)` for each
  child blueprint, called from the api package. HTML blueprints remain
  CSRF-protected; verified by a POST test returning 400 for
  unauthenticated HTML, 401 for the API.
- **Wildcard CORS removed.** `CORS(app, resources={"/api/*": {"origins": "*"}})`
  provided no benefit (no browser client) and combined with Bearer
  tokens was a hazard if a token leaked. Removed.

### Notes
- `services.campaigns.resolve_recipients` already enforced `OptOut`
  for `custom_phones` — no fix needed there.
- `services.entitlements.check_can_send` already enforced
  `org.status == 'active'` — no fix needed there.
- Runtime test for C1 (cross-tenant channel access) requires two
  orgs with separate users. Deferred to first multi-tenant deploy.
- Three H-tier items from the API audit remain: idempotency under
  concurrency, keyset pagination on list endpoints, and rate limiting
  on `/auth/login`.

## [0.10.0] — Plan pricing revision; credits never expire

### Changed
- **Retail rates lowered across every tier.** Starter 50→45,
  Growth 45→40, Business 40→35, Scale 35→30. Margin is now a flat
  UGX 10 per SMS on every tier (previously 15 on Starter, 10 elsewhere).
- **Plans are one-time purchases with no expiry.** `Plan.validity_days`
  is set to `36500` (100 years) as a perpetual sentinel. The display
  layer renders "No expiry" for any value at or above that.
- **Existing plans deactivated, new plans inserted.** Per the
  grandfathering rule in `docs/PRICING.md`. Existing subscribers keep
  the prior rate until renewal.

### Added
- `scripts/update_prices_2026_10.py` — one-shot migration script.
  Dry-run by default, requires `--apply` to commit. Idempotent.

### Why
- The 0.7.1 increase took a 5 UGX buffer per SMS to cover wholesale
  variance. Flat 10 UGX per tier achieves the same buffer with a
  cleaner structure.
- Retail bands now align with Pahappa's wholesale bands, so the
  advertised band matches the plan's actual pricing tier.
- Credits never expiring simplifies the associate's mental model: buy
  once, use whenever.

### Notes
- Enterprise tier (600,000+ credits) is quoted manually by the master.
  Not represented as a `Plan` row.
- The public pricing page shows four tiers (Starter, Growth, Business,
  Scale).
- Balance display: unchanged. Credits are still UGX-priced in the UI,
  using the org's plan rate.
  
## [0.9.1] — Opt-out link removed from outbound messages

### Changed
- **Messages no longer carry an automatic opt-out link.** `render()`
  now produces only `prefix + body`. See ADR-017.
- Message cost drops for short messages that previously tipped into a
  second segment because of the ~76-character opt-out line.
- The client-side character counter on the new-campaign form is now
  accurate. It previously under-counted by ~76 characters because it
  did not include the opt-out URL that the server appended.

### Why
- The link added real cost to every message.
- Recipients read it as a spam signal.
- Opt-outs are now the associate's responsibility, documented in the
  associate agreement.

### Notes
- The public landing page at `/opt-out` and the `OptOut` table remain
  in place and are still enforced across every send path.
- Existing delivered messages keep their opt-out links. Nothing is
  retroactive.
- ADR-004 is superseded by ADR-017.

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