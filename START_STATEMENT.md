# Roman SMS — session start statement

I'm continuing work on Roman SMS, a Flask SMS reseller platform with a
Flutter Android client, running on a single DigitalOcean VPS.

## Where I left off (end of session 2026-10-28)

**Branch:** `wip/mobile-api` at commit `9766913` — pushed to GitHub.
Working tree is clean. Nothing is in-flight.

**Production:** The mobile API is live and verified at
`https://romansms.com/api/v1/*`. All 17 routes tested end-to-end with
real curl requests and real users. Login, signup, wallet, plans, chat,
notifications all return real data.

**Flutter app:** Working on a physical Android device against production.
APK built with `flutter build apk --release`, installed manually. Login,
signup, wallet, plans, chat, and full navigation all functional.

## What got fixed in the previous session

Eight real bugs, all of which were live on production until fixed:

1. **Boot crash** — `create_app()` raised `AttributeError: 'Flask'
   object has no attribute 'unauthorized_handler'`. Fixed in `89593c7`.
   The entire `/api/v1/*` tree was unreachable before this.
2. **CSRF exemption** — a monkey-patch on `csrf.protect` was replaced
   with per-child-blueprint `csrf.exempt(child_bp)` in
   `app/api/v1/__init__.py`. Flask-WTF does not cascade exemptions
   from a parent blueprint to children.
3. **Wildcard CORS** — removed. No browser client exists; wildcard
   CORS on a Bearer-authenticated API was a hazard.
4. **Chat cross-tenant leak** — `channels()`, `messages(cid)`, and
   `send_message(cid)` had no org scoping. Any associate could read
   another org's DM by iterating channel IDs. Fixed with
   `_channel_visible_or_404(cid)`.
5. **Wallet wrong function** — `entitlements.balance()` was called;
   the real function is `entitlements.get_balance()`. `/wallet` had
   been 500-ing on every request since written.
6. **Campaign paste triple-bug** — called nonexistent
   `resolve_pasted_numbers`, passed `synthetic_contacts=` (should be
   `custom_phones=`), didn't unpack `(campaign, total_segments)` tuple.
7. **Campaign serializer zeros** — read `c.recipient_count` /
   `c.cost_credits`; model has `total` / `credits_debited`.
8. **Plans wrong columns** — read `p.price_ugx` / `p.rate_ugx`; model
   has `price` and derives `rate = price / credits`.

## Commits from the previous session
9766913 chore(mobile): remove linux/macos/windows/web scaffolding
4fc8392 feat(mobile): track full Flutter app
11c2d4f docs: ADRs 020-022; Mobile API; MOBILE.md; index updates
69d99d9 feat(api): add POST /api/v1/auth/signup
c012d5f fix(api): wallet.summary calls entitlements.get_balance
32787bf fix(api): /plans uses real Plan columns
...
89593c7 fix(app): use login_manager.unauthorized_handler


## Key docs (all in repo, synced between `docs/` and root)

- **`ARCHITECTURE.md`** — now has a `## Mobile API` section with the
  invariants: `org_id` never from request, decimal fields serialize
  as strings, CSRF exempt per-child, campaign creation requires
  `Idempotency-Key`.
- **`DECISIONS.md`** — ADRs 001 through 022. Three new from last
  session:
  - `ADR-019` — API code must be written against real models, not
    against mental models of the codebase.
  - `ADR-020` — Associate-only mobile; master console stays web-only.
  - `ADR-021` — Full mobile feature parity with the web console,
    planned as 15 sequential rounds over ~10 focused days.
  - `ADR-022` — Flutter base URL via `--dart-define`; `INTERNET`
    permission in `android/app/src/main/AndroidManifest.xml`.
- **`CHANGELOG.md`** — `## [0.12.0]` documents what shipped and, more
  importantly, what's deferred.
- **`MOBILE.md`** (new) — Flutter developer reference.
- **`DEPLOY.md`** — has a `## Current production deployment`
  section documenting the *actual* state (user `oyomthorm`, path
  `/srv/roman-sms`, Postgres on TCP with role `roman`, etc.).
- **`README.md`** — index updated with `MOBILE.md`.

## What's deferred (documented in CHANGELOG 0.12.0 "Discovered, not fixed")

- **SMTP is unconfigured on production.** `MAIL_SERVER`,
  `MAIL_USERNAME`, `MAIL_PASSWORD`, `ALERT_EMAIL` are empty or absent
  in `/srv/roman-sms/.env`. Signup applications land in `signup_requests`
  table but neither applicant nor master receives any email. **This is
  documented and accepted** — signup is functionally complete,
  notification is not. Fix: configure SendGrid or similar, ~20 min.
- **Missing endpoints** (all documented): `POST/GET /api/v1/invoices`,
  `GET /api/v1/campaigns/<id>`, `GET /api/v1/dashboard`,
  `PATCH/DELETE /api/v1/contacts/<id>`, `POST /api/v1/contacts/<id>/optout`,
  groups CRUD, schedules CRUD, `PUT /api/v1/auth/profile`,
  `POST /api/v1/auth/change-password`.
- **Flutter screens using mock data**: `dashboardStatsProvider` returns
  hardcoded `sent_30d: 12450, delivery_rate: '98.2%'`. Profile screen
  shows hardcoded "admin@example.com".

## Deployment state

**VPS:** DigitalOcean droplet `ubuntu-s5-2vcpu-4gb-30gb-mkc1`,
`165.245.199.37`. Running Ubuntu 24.04. Postgres 16.
- App at `/srv/roman-sms/`, user `oyomthorm`, services run as
  `User=oyomthorm Group=www-data`.
- Postgres role `roman`, DB `roman_sms`, TCP on `127.0.0.1:5432`.
- systemd units: `roman-sms.service` (gunicorn, 3 workers, `127.0.0.1:8000`),
  `roman-worker.service` (`python worker.py`).
- Nginx reverse proxy + Let's Encrypt SSL on `https://romansms.com`.
- Last deployed commit: `69d99d9` (the mobile API signup endpoint +
  earlier C-fixes). **Not yet deployed:** the docs-only commits
  (`11c2d4f`, `4fc8392`, `9766913`) — these touch `mobile/` and `docs/`
  only and don't affect the running API.

**Backup tag:** `pre-mobile-api-deploy` at `ddc93cf` — the last
known-good state before the mobile API deploy.

## Test account

`associate@romansms.com` / `TempAssociate2026!` — an associate_admin
in the `test-associate` org (id 5), with 1000 SMS on the Starter plan
(45 UGX/SMS, UGX 45,000 value). This is a real account with real
credits — useful for testing. **Change the password before any real
customer is onboarded.**

Master admin: `admin@romansms.local` / `AdminTempPass2026!`. Used for
master-console web access. Same password-hygiene note applies.

## Plan for today

Per **ADR-021**, work through the mobile parity roadmap one round at
a time. **Round 1 (next): Contacts CRUD.**

- **Backend** (~1h): three new endpoints wrapping existing services:
  - `PATCH /api/v1/contacts/<id>` → `services.contacts.update_contact`
  - `DELETE /api/v1/contacts/<id>` → `services.contacts.delete_contact`
  - `POST /api/v1/contacts/<id>/optout` → `services.contacts.mark_opted_out`
- **Flutter** (~2h): contact detail screen (tap contact in list →
  view/edit/opt-out/delete). Verify `add_contact_sheet.dart` posts
  correctly.
- **Test**: on the phone, from the associate account. Verify create,
  edit, delete, opt-out all work against production.
- **Commit**: one commit for backend, one for Flutter. Push.

Rounds 2–15 follow. Each round is self-contained: backend endpoints
(wrapping existing services), Flutter screens, test on the device,
commit, push. **One round per session** unless momentum carries.

## Working style that works (learned over many sessions)

1. **Inspect before writing.** For any fix touching services or models,
   `Get-Content` the current file first. Never write a serializer
   field or service call from memory — that's exactly the class of bug
   `ADR-019` documents.
2. **Small chunks for large edits.** PowerShell here-strings with
   large content occasionally get truncated on paste and crash the
   terminal. Split into 5–10 line `Add-Content` calls, verify after
   each.
3. **Precondition checks before destructive actions.** `git diff
   --quiet <file>` before fixing. Test file writes land before commit.
   If a script writes and fails, verify the rollback worked.
4. **One commit per logical unit.** "docs:", "feat(api):",
   "fix(api):", "chore(mobile):". Never `git add .` on a dirty tree
   with unrelated noise.
5. **Verify the actual thing, not a proxy.** Probe the live endpoint
   with real curl. Install the APK on a real phone. Look at the drawer
   in the running app. The "it looks right" failures this session were
   all caught by probing reality.
6. **Stop when the state is clean.** A session ends with a pushed
   branch, clean working tree, and no half-applied changes. Not "we'll
   finish it tomorrow" — actually clean.

## First action of today's session

1. `cd D:\Dev_Apps\roman_sms`
2. `git fetch origin wip/mobile-api`
3. `git pull origin wip/mobile-api` — confirm at `9766913`
4. `git status --short` — expect clean (only the untracked
   `docs/Roman_Panel_Documentation_Formatted.md` if not yet ignored)
5. Paste the outputs of the above.

Then start Round 1: read `app/api/v1/contacts.py` and
`app/services/contacts.py` (in full) to see what `update_contact`,
`delete_contact`, `mark_opted_out` look like. From that, write the
backend endpoints. From the endpoints, write the Flutter screen.

**No commits until the round's tests pass on the phone.**

## What I need from the assistant today

- Same discipline as always: inspect before writing, one round at a
  time, verify on the real device, commit cleanly, push.
- When something fails, isolate the specific layer (client, server,
  network, encoding) before changing code. Do not guess.
- Use the `fix_*.py` / `Add-Content` pattern proven to work. Do not
  use large here-string scripts that might get truncated.
- Flag when a step is skipped (like the earlier `Remove-Item` on
  platform folders that was skipped and had to be redone).
- Honest scope estimates. If Round 1 turns out to be 3 hours instead
  of 2, say so before starting.

Start with the five git commands above. Paste the outputs. Then we
begin Round 1.