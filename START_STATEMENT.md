# Roman SMS — session start statement

I'm continuing work on Roman SMS, a Flask SMS reseller platform with a
Flutter Android client, running on a single DigitalOcean VPS.

## Where I left off (end of session 2026-10-29)

**Branch:** `wip/mobile-api` at commit `4dfe02c` — pushed to GitHub.
Working tree is clean. Nothing is in-flight.

**Production:** The mobile API is live and verified at
`https://romansms.com/api/v1/*`. Login, wallet, plans, chat, notifications
all return real data.

**Flutter app:** Working on a physical Android device against production.

**Database:** Clean, migrated (`00404835aeb7`), and freshly seeded via
`flask seed-all`. 1 admin, 2 orgs, 4 plans, 132 districts.

**Pahappa / EgoSMS:** Live production credentials connected. `EGOSMS_SANDBOX=0`
in `/srv/roman-sms/.env`. Master wallet balance is synced with the live
Pahappa balance (verified at 1,080 credits).

**Roman Panel:** A separate Flask control panel (`/srv/roman-panel/`) is
running on `127.0.0.1:8080` (accessible via SSH tunnel). It has system
resource bars (CPU/RAM/Disk), database analytics (associates, contacts,
messages, campaigns, master wallet), quick actions (restart nginx, vacuum
DB, check Pahappa), live logs, and git uptime display. Code is mirrored
in the main repo at `panel/`.

## What got fixed in the previous session (2026-10-29)

1. **Secret Hygiene:** Moved `scripts/VPS ROOT.txt` (live Pahappa/panel
   credentials) out of the repo tree to `D:\Secrets\roman_sms\`. Updated
   `.gitignore` to prevent tracking it or scratch docs.
2. **Database Recovery:** Production DB was in a broken state (alembic
   stamped but tables absent). Recovered from a pre-reset `pg_dump`,
   wiped clean, migrated, and re-seeded.
3. **Pahappa / EgoSMS Integration:** Diagnosed "Wrong Username or Password"
   as a sandbox-vs-production endpoint mismatch. Flipped `EGOSMS_SANDBOX=0`
   to use live credentials. Fixed a boolean parsing bug in `egosms_client.py`.
4. **Roman Panel:** Located, integrated into the main repo, and enhanced
   with analytics + quick actions.
5. **Git Cohesion:** Set up SSH key auth for VPS → GitHub. Merged VPS and
   laptop history cleanly (`.gitignore` conflict resolved).

## What got fixed in the session before that (2026-10-28)

Eight real bugs, all of which were live on production until fixed:

1. **Boot crash** — `create_app()` raised `AttributeError: 'Flask'
   object has no attribute 'unauthorized_handler'`. Fixed in `89593c7`.
2. **CSRF exemption** — per-child-blueprint `csrf.exempt(child_bp)` in
   `app/api/v1/__init__.py`. Flask-WTF does not cascade from parent.
3. **Wildcard CORS** — removed.
4. **Chat cross-tenant leak** — `_channel_visible_or_404(cid)` added.
5. **Wallet wrong function** — `entitlements.get_balance()`.
6. **Campaign paste triple-bug** — fixed.
7. **Campaign serializer zeros** — fixed.
8. **Plans wrong columns** — fixed.

## Key docs (all in repo, synced between `docs/` and root)

- **`ARCHITECTURE.md`** — `## Mobile API` section with invariants.
- **`DECISIONS.md`** — ADRs 001 through 022. ADRs 019–022 are the
  mobile-era decisions.
- **`CHANGELOG.md`** — `## [0.12.0]` documents what shipped and deferred.
- **`MOBILE.md`** — Flutter developer reference.
- **`DEPLOY.md`** — current production deployment section.
- **`README.md`** — index updated with `MOBILE.md`.

## What's deferred

- **SMTP unconfigured on production.** Signup applications land in
  `signup_requests` but no emails send. Fix: configure SendGrid (~20 min).
- **Missing endpoints:** `POST/GET /api/v1/invoices`,
  `GET /api/v1/campaigns/<id>`, `GET /api/v1/dashboard`,
  `PATCH/DELETE /api/v1/contacts/<id>`,
  `POST /api/v1/contacts/<id>/optout`, groups CRUD, schedules CRUD,
  `PUT /api/v1/auth/profile`, `POST /api/v1/auth/change-password`.
- **Flutter screens using mock data:** `dashboardStatsProvider` returns
  hardcoded stats. Profile screen shows hardcoded email.

## Deployment state

**VPS:** DigitalOcean droplet `ubuntu-s5-2vcpu-4gb-30gb-mkc1`,
`165.245.199.37`. Running Ubuntu 24.04. Postgres 16.
- App at `/srv/roman-sms/`, user `oyomthorm`, services run as
  `User=oyomthorm Group=www-data`.
- Postgres role `roman`, DB `roman_sms`, TCP on `127.0.0.1:5432`.
- systemd units: `roman-sms.service` (gunicorn, 3 workers, `127.0.0.1:8000`),
  `roman-worker.service` (`python worker.py`),
  `roman-panel.service` (Flask panel, `127.0.0.1:8080`).
- Nginx reverse proxy + Let's Encrypt SSL on `https://romansms.com`.

**Backups:** `/srv/roman-sms/backups/` contains:
- `roman_sms_pre_reset_20261029_200238_PRODUCTION.dump` (pre-wipe state,
  28 tables with data — contains the original test associate account)
- Daily cron `auto_YYYY-MM-DD.sql` at 03:00 UTC (schema only — 0 data rows)
- **Known issue:** cron backups are schema-only. Ad-hoc `pg_dump` needs
  `chown postgres /srv/roman-sms/backups` to write. Fix when convenient.

**Backup tag:** `pre-mobile-api-deploy` at `ddc93cf`.

## Test accounts

- **Master admin:** `admin@romansms.local` / `ChangeMe123!` (seed default —
  change before production customers).
- **Associate:** `associate@romansms.com` / `TempAssociate2026!` — created
  manually after the wipe. Belongs to org `test-associate` with 1,000 credits.

**Both passwords are in this document. Change both before any real customer
is onboarded.**

## Plan for today

Per **ADR-021**, work through the mobile parity roadmap one round at a
time. **Round 1 (next): Contacts CRUD.**

- **Backend** (~1h): three new endpoints wrapping existing services:
  - `PATCH /api/v1/contacts/<id>` → `services.contacts.update_contact`
  - `DELETE /api/v1/contacts/<id>` → `services.contacts.delete_contact`
  - `POST /api/v1/contacts/<id>/optout` → `services.contacts.mark_opted_out`
  - **Route note:** normalize `null` group_id/district_id into
    `clear_group=True` / `clear_district=True` before calling the service
    (the service uses those kwargs, not nulls).
- **Flutter** (~2h): contact detail screen (tap contact in list →
  view/edit/opt-out/delete). Verify `add_contact_sheet.dart` posts
  correctly.
- **Test**: on the phone, from `associate@romansms.com`. Verify create,
  edit, delete, opt-out all work against production.
- **Commit**: one commit for backend, one for Flutter. Push.

Rounds 2–15 follow. One round per session unless momentum carries.

## Working style that works (learned over many sessions)

1. **Inspect before writing.** `Get-Content` the current file first.
   Never write a serializer field or service call from memory — that's
   the class of bug ADR-019 documents.
2. **Small chunks for large edits.** Split into 5–10 line `Add-Content`
   calls, verify after each.
3. **Precondition checks before destructive actions.** `git diff --quiet`
   before fixing. Test file writes land before commit.
4. **One commit per logical unit.** `docs:`, `feat(api):`, `fix(api):`,
   `chore(mobile):`. Never `git add .` on a dirty tree.
5. **Verify the actual thing, not a proxy.** Probe the live endpoint
   with real curl. Install the APK on the real phone.
6. **Stop when the state is clean.** Pushed branch, clean tree, no
   half-applied changes.

## First action of today's session

1. `cd D:\Dev_Apps\roman_sms`
2. `git fetch origin wip/mobile-api`
3. `git pull origin wip/mobile-api` — confirm at `4dfe02c`
4. `git status --short` — expect clean
5. Paste the outputs of the above.

Then start Round 1: read `app/api/v1/contacts.py`,
`app/services/contacts.py`, and `app/api/v1/serializers.py` (the
`contact()` function, to confirm `opted_out` is exposed). From that,
write the backend endpoints. From the endpoints, write the Flutter screen.

**No commits until the round's tests pass on the phone.**

## What I need from the assistant today

- Same discipline as always: inspect before writing, one round at a
  time, verify on the real device, commit cleanly, push.
- When something fails, isolate the specific layer (client, server,
  network, encoding) before changing code. Do not guess.
- Use the `fix_*.py` / `Add-Content` pattern proven to work. Do not
  use large here-string scripts that might get truncated.
- Flag when a step is skipped.
- Honest scope estimates. If Round 1 turns out to be 3 hours instead
  of 2, say so before starting.

Start with the five git commands above. Paste the outputs. Then we
begin Round 1.