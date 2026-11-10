# Roman SMS — session start statement

I'm continuing work on Roman SMS, a Flask SMS reseller platform with a
Flutter Android client, running on a single DigitalOcean VPS.

## Where I left off (end of session 2026-11-13)

**Branch:** `wip/mobile-api` at `1cec53c` (mobile lint cleanup) — pushed
to GitHub. Working tree is clean. Nothing in-flight.

**Production (LIVE, UNCHANGED this session):**
- VPS at `8a71f6b` (last code commit before docs; docs and mobile
  commits don't deploy). **Not touched this session — mobile work is
  client-side only.**
- Migration `87cd66d8578c` applied. Unchanged since #45.
- Services active: `roman-sms.service`, `roman-worker.service`,
  `roman-panel.service`.
- Mobile API live at `https://romansms.com/api/v1/*`. No endpoint
  changes since `6b07d67`.
- Full onboarding flow verified end to end (2026-11-13).

**Flutter app:** Static analysis cleaned this session. 6 commits landed:
lint infrastructure added, mojibake fixed, error messages fixed, router
churn fixed, 11 lint items fixed, 3 redundant-const items fixed.
`flutter analyze` went from 10 issues to **4 issues (all `Radio.*`
deprecations, deferred)**. Release APK built and **installed on the
physical device** but **not yet runtime-tested** — that's the next
session's first concrete task.

**Database (prod):** Migrated to `87cd66d8578c`. Five orgs, four users.
Two real customers: Fitting (school, schedule #1 fires through
2026-11-29) and ORONEK (business, 0 contacts as of last check).

**Database (local):** Migrated to `87cd66d8578c`. Seeded with test
fixtures (org ids differ from prod; `tasms` is id 5 locally, id 4 in
prod).

## What got done this session (2026-11-13 mobile arc)

The Flutter health check split cleanly into two phases. **Static phase
complete. Runtime phase not started.**

**Six commits on `wip/mobile-api`:**

| Commit | Change | `flutter analyze` after |
|---|---|---|
| `d4e1d04` | Add `flutter_lints` + `flutter_test`; fix dashboard mojibake | 15 |
| `bc04bae` | Router churn fix (`_authStatusProvider`), user-facing error strings | 15 |
| `3cd4b62` | Paste 3a: 7 trivial lint fixes | 8 |
| `859bf3b` | Paste 3b: 4 `const` additions | 7 (net 4 fixed, 3 new) |
| `1cec53c` | Paste 3c: 3 redundant-`const` removals | **4** |

**Issue reduction: 10 → 4.** Remaining 4 are `Radio.groupValue` /
`Radio.onChanged` deprecations in `new_campaign_screen.dart:167,168,176,177`.
Deferred — proper fix requires migrating to `RadioGroup` widget.

**What actually got fixed (from the deferred list):**
- #3 Dashboard "Hello, Admin" hardcoded — **NOT fixed** (this was in the
  START_STATEMENT but the mobile source had already moved to a
  different presentation; only the mojibake string `"Roman SMS â€¢
  Verified"` was replaced with `"Verified"`). The `Hello, Admin` string
  remains in the source and was not touched. Defer to runtime testing
  to confirm what the user actually sees.
- #4 Dashboard header mojibake — **fixed** (replaced `"Roman SMS â€¢
  Verified"` with `"Verified"`; full org-name replacement deferred until
  runtime shape of `org['name']` is confirmed).
- #6 `withOpacity` deprecation (3 occurrences) — **fixed** (all now
  `withValues(alpha:)`).
- #7 Unused `go_router` import — **fixed**.
- #8 Router churn — **fixed** (`routerProvider` now watches only
  `isAuthenticated` via `_authStatusProvider`).
- #20 `CupertinoIcons` referenced but not in pubspec — **not fixed, not
  needed**. Source grep confirmed zero `CupertinoIcons` usage. No build
  error. Off the list.
- #21 `flutter_lints/flutter.yaml` include can't resolve — **fixed**
  (`flutter_lints: ^4.0.0` added to `dev_dependencies`; `flutter pub get`
  ran; analyzer now loads the ruleset).
- #22 Unused local `r` in `new_campaign_screen.dart:86` — **fixed** (line
  56's `r` preserved; line 86's `r` removed; verified by scoping the
  anchor to `/api/v1/campaigns` not `/api/v1/campaigns/preview`).
- #28 `Radio.groupValue/onChanged` deprecation — **deferred**. 4 items.
  Structural refactor. Not a runtime bug; will break in Flutter SDK 4.0.

**Also fixed (not on the prior list):**
- Dev-mode error strings in `auth_provider.dart` — "The phone cannot
  reach the laptop" and "Windows Firewall is blocking the port" replaced
  with user-appropriate text. 401-specific branch added.
- `login_screen.dart:20` — curly braces added to single-statement `if`.
- `wallet_screen.dart:101` — redundant `${delta}` braces removed.
- 4 `prefer_const_constructors` — `const` added to `CircleAvatar` and
  `Icon` constructors.

**What broke and was reverted (net zero on the tree):**
- First attempt at paste 2 wrote `== 401 {` (missing closing `)`). The
  revert-on-error gate fired on the new `expected_token` error, all six
  files reverted, retried with correct syntax.
- Two attempts at paste 3b's `new_campaign_screen.dart` mutation
  corrupted the file — first by blanket `.Replace()` matching two
  occurrences when only one was intended (reverted), second by an
  anchor whose line-count check failed (aborted before write, no
  damage). Third attempt succeeded with line-index mutation.

**Test progression:** no new tests written — this session was lint
cleanup and router refactor, not feature work. Test count unchanged at
**247 passing**.

## What's next

Pick from (no blockers between them):

**(a) Flutter runtime health check** — **partially done this session.**
The APK is installed on the physical device. Static analysis is clean.
The runtime phase — launching the app, logging in, walking through each
of the 20 screens, exercising add/edit/delete flows, verifying polling
and logout/login — **has not started.** This is the highest-value next
task because it's the only way to find the runtime bugs that static
analysis cannot catch. **My recommendation** — highest value because
the entire reason for the health check was to surface behavioral issues.

**(b) #50 passwordless sudo for specific systemctl commands** — 5-min
win. Every deploy costs a sudo prompt. Add to `/etc/sudoers.d/`:
`oyomthorm ALL=(ALL) NOPASSWD: /bin/systemctl restart roman-sms,
/bin/systemctl restart roman-worker, /bin/systemctl restart roman-panel,
/bin/systemctl is-active *`

**(c) #38 user delete FK migration** — 4 NOT NULL FKs block user
deletion (chat_read_state, chat_message, notification_dismissal,
pool_permission.granted_by). No customer has asked; but if one does,
delete via `/school/users/<id>/delete` will fail. Add migration with
`ON DELETE CASCADE` on those four, `ON DELETE SET NULL` on the ten
nullable ones. ~1 session.

**(d) #39 RUNBOOK CLI verification note** — document the CLI verification
pattern used for #16 and A5. ~1 hour.

**(e) #51 onboarding copy varies by vertical** — the #45 foundation
enables different welcome emails for school vs business. Currently both
get the same generic email. Nice UX; not urgent.

**(f) #32 pahappa_sync drift fix** — clicking "Sync to Pahappa" credits
the master wallet for the total balance difference, without provenance.
Deferred since before A1.

## Deferred / known issues (carry forward — reconciled)

**From the mobile-only arc (still open after this session):**

1. Panel grant form bug (500 entered → 10 saved). *Runtime — verify
   on device next session.*
2. Empty `recent_activity` renders zero-height Card on dashboard.
   *Runtime — verify on device.*
3. Dashboard "Hello, Admin" hardcoded in `dashboard_screen.dart`.
   *Still present in source; needs runtime check to see if user actually
   sees "Admin".*
4. Master org users hitting `/api/v1/dashboard` get master-org stats.
   *Server-side — separate from mobile app. Verify with master account
   on device.*
5. Password dialog error handling uses `contains('422')`. *Runtime —
   code smell, verify on device.*
6. `_refresh()` in `ContactDetailScreen` uses bare `catch (_)`. *Code
   smell — invisible to user, leaves API errors only in logs.*
7. `DELETE /contacts/<id>` is hard delete — no undo. *By design; user
   must confirm before delete.*
8. `update_contact` clear_group/clear_district untested with non-null.
   *Runtime — verify by editing a contact's group on device.*
9. Contacts endpoint error taxonomy inconsistent. *Server-side; verify
   by triggering an error.*
10. Campaign detail polish. *Cosmetic — verify on device.*
11. Contact detail district picker (no API round exists yet). *Feature
    gap — no UI for setting district on existing contact.*
12. `iso()` emits naive datetimes without `Z` — cross-cutting. *Server
    response format; mobile parses but display may be ambiguous for
    non-UTC users.*
13. `audit.log()` commits own transaction, swallows exceptions.
    *Server-side; documented behavior, not a bug.*
14. `svc.delete(group)` doesn't guard referenced `Schedule.group_id`.
    *Runtime — verify by deleting a group referenced by a schedule.*
15. `GET /groups/<id>` returns `contact_count: null` by design. *Server
    contract — mobile handles null correctly.*
16. `contacts_screen.dart` name-empty fallback — pre-existing display
    bug. *Runtime — verify by adding a contact with no name.*
17. `add_contact(None, ...)` raises `AttributeError` on `org.id`. *Edge
    case; test coverage gap.*
18. Test fixtures leak on mid-run crash — `test_groups_api.py` has no
    try/finally. *Test infrastructure.*
19. `contacts/form.html` phone field readonly by design — add hint.
    *Web-side UI, not mobile.*
20. Group detail actions icons — cosmetic polish. *Mobile UI — verify on
    device.*

**Fixed this session (moved out of the deferred list):**
- ~~`withOpacity` deprecation~~ — all 3 fixed.
- ~~Unused `go_router` import~~ — fixed.
- ~~Router churn~~ — fixed.
- ~~`flutter_lints/flutter.yaml` include can't resolve~~ — fixed.
- ~~Unused local `r` in `new_campaign_screen.dart:86`~~ — fixed.

**Removed from deferred (not needed):**
- ~~`CupertinoIcons` referenced but `cupertino_icons` not in pubspec~~ —
  no `CupertinoIcons` usage found in source. Not a build issue.

**Still deferred (mobile):**
- `Radio.groupValue/onChanged` deprecations (4 items,
  `new_campaign_screen.dart:167,168,176,177`). Migration to `RadioGroup`
  widget. Deferred until Flutter SDK 4.0 upgrade.
- Base URL `--dart-define` parameterization. Works against prod today;
  blocks staging. Small fix, deferred.
- `usesCleartextTraffic="true"` in AndroidManifest — vestigial; no
  security impact since production URL is HTTPS.

**From prior arcs (still open):**
- #50 passwordless sudo (5-min).
- #38 user delete FK migration.
- #39 RUNBOOK CLI verification note.
- #51 onboarding copy varies by vertical (deferred).
- #32 pahappa_sync drift fix (deferred).
- #43 self-service plan purchase (deferred).

## Working style that works

1. **Inspect before writing.** Never serialize a field or call a service
   from memory. Enumerate files (Get-ChildItem -Recurse) before editing
   a class. `inspect.getsource()` proves existence, not file location.
2. **Single-write-gate for multi-file pastes.** Read all files → verify
   all anchors → apply all mutations in memory → verify mutations →
   write all → verify on disk. Any failure before write leaves zero disk
   changes.
3. **EOL awareness.** Files may be CRLF or LF. Use `IndexOf` on
   single-line substrings for EOL-agnostic anchors. Position-based
   insertion (LastIndexOf) beats multi-line literal replace for templates.
4. **Phantom file detection.** After any multi-file paste, `git status
   --short`. Any unexpected `??` file is a bug in the paste. Delete and
   investigate.
5. **Test fixture tracing.** Trace mutations to the assertion point,
   not the function entry.
6. **A throw in a pasted line does not stop later lines.** The mutation
   must be the last line of the paste, or inside an `if/else` where the
   `else` contains the mutation.
7. **Test first, commit second.** Never commit on the assumption that
   tests pass — run them, paste the exit code, then commit.
8. **Feature arc: inspect → design confirm → write paste → verify →
   browser/CLI verification → commit → deploy.**
9. **Verification vs. feature sessions are different.** Both are
   valuable.

**New rules from this session (mobile arc):**

10. **Revert-on-error gate for any code-modifying paste.** After any
    paste that mutates source files, run `flutter analyze` (or equivalent
    for the language) and if the tool reports a new **error** — not
    warning, not info — `git checkout --` the modified files before
    diagnosing. Warnings and infos can stay; errors mean a bad paste,
    full stop. Revert is 2 seconds; diagnosing a broken state is 20
    minutes.
11. **Occurrence count checks before any blanket `.Replace()`.** If a
    target string might appear more than once, count it with
    `-ceq`-on-split-lines (not `[regex]::Matches` — regex escape on
    newlines fails silently). If count ≠ 1, abort before mutation.
    Anchors with unique surrounding context avoid the multi-occurrence
    problem entirely.
12. **Absolute paths for `[System.IO.File]`.** `ReadAllText("lib/foo")`
    resolves against process CWD, not PowerShell's `$PWD`. Always pass
    absolute paths. `Get-Content` respects `$PWD`; `[System.IO.File]`
    does not.
13. **Line-index mutation for single-line edits.** Split file into
    lines, mutate by index with `.Trim()` verification, rejoin with
    known EOL. This is more reliable than file-wide `.Replace()` for
    single-line edits, especially when the file has multiple similar
    lines.
14. **Byte-level verification of `flutter analyze` results.** The
    counts reported by `flutter analyze` (10 → 15 → 8 → 7 → 4) were the
    only reliable signal that each paste worked or failed. String
    presence is not enough — the analyzer's issue count is the actual
    health metric.
15. **When a rendered artifact looks broken, hard-refresh first.**
    `Ctrl+Shift+R` + `file:///` URL bypasses cache. In this session and
    the docs arc, "broken rendering" was three times stale browser
    cache, not a file problem.

## Test accounts

**Master admin:** `admin@romansms.local` / `ChangeMe123!`
**Associate:** `associate@romansms.com` / `Temp2026!`
  - **Prod:** org `TempAssoc` (id 4, slug `tasms`)
  - **Local:** org `tasms` (id 5)

**Change passwords before production customers.**

## Local test fixtures

**Local DB (org ids differ from prod; `tasms` = id 5 locally, id 4 in prod):**
- Users: `admin@romansms.local` (org 1), `admin@test.com` (org 1),
  `oyomthorm.21@gmail.com` (org 3), `associate@romansms.com` (org 5,
  `TempAssociate2026!` — **local password differs from prod**).
- Orgs: `roman-sms` (1), `roman-platform` (2), `roman-computer-services` (3),
  `tasms` (5).
- Group: `Franco Intro` (id 25, org 5) with 1 contact.
- Contact: `256700000001` "Test Contact A" (id 14, group 25).

**Prod DB (production state):**
- Orgs: `Roman SMS` (1, master), `Roman SMS Platform` (2, system),
  `Fitting` (3, school), `TempAssoc` (4, slug `tasms`), `ORONEK` (5, slug
  `orsms`, business).
- `Fitting`: schedule #1 "Franco Intro" has 6 remaining runs through
  2026-11-29.
- `tasms`: 166 contacts, wallet ~844.
- `orsms`: 0 contacts, 1 user (`oronek1984@gmail.com`), vertical=business.
- Associate user in prod org 4, password `Temp2026!`.

## Deployment state

**VPS:** DigitalOcean droplet `ubuntu-s5-2vcpu-4gb-30gb-mkc1`,
`165.245.199.37`. Ubuntu 24.04. Postgres 16.
- App at `/srv/roman-sms/`, user `oyomthorm`.
- systemd: `roman-sms.service` (gunicorn, 3 workers, `127.0.0.1:8000`),
  `roman-worker.service`, `roman-panel.service` (Flask panel on
  `127.0.0.1:8080`).
- Nginx + Let's Encrypt SSL on `https://romansms.com`.
- **Currently at `8a71f6b` (app); unchanged this session.**
- SSH key auth for `oyomthorm` — no password prompt on `ssh`. `sudo`
  still prompts — use `ssh -t`.

**Backups:** `/srv/roman-sms/backups/` — daily cron at 03:00 UTC, schema
only. Pre-department rollback backup at
`/srv/roman-sms/backups/pre_department_2026_11_09.sql` (508 KB, verified
2026-11-09, contains 28 `CREATE TABLE` statements).

**SMTP:** Mailgun on port 2525 (DigitalOcean blocks 25/465/587). Domain
`mg.romansms.com` verified via DNS TXT records. Works end to end.

## First action of next session

1. `cd D:\Dev_Apps\roman_sms`
2. `git fetch origin wip/mobile-api`
3. `git pull origin wip/mobile-api` — confirm at `1cec53c` (or later)
4. `git status --short` — expect clean
5. Confirm VPS is at `8a71f6b` and services active
6. **Pick (a) first.**

**Recommended: (a) Flutter runtime health check.** Static analysis is
clean (4 deferred deprecations, no warnings, no errors). APK is built
and installed on the phone. The runtime phase — launching the app,
exercising login → dashboard → every screen → add/edit/delete flows →
chat polling → logout/login — **has not started.** This is the single
highest-value remaining task because static analysis cannot catch the
runtime bugs the START_STATEMENT originally flagged (panel grant form
bug, empty `recent_activity`, master org stats, etc.).

The runtime test plan is documented in the prior session's log if
needed, but the essential sequence is: open app → login with
`admin@romansms.local` / `ChangeMe123!` → dashboard renders → tap each
bottom nav item → tap each drill-down → attempt add/edit/delete →
attempt wrong-password login → attempt logout/login. Report per-screen:
OK / SLOW / BLANK / ERROR / CRASH. For anything that isn't OK, capture
the visible error text or the last-rendered state before any crash.

**No migration pending. No deploy planned.** This session was client-side
only; the VPS is untouched and stable.