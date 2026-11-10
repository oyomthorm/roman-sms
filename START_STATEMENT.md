# Roman SMS — session start statement

I'm continuing work on Roman SMS, a Flask SMS reseller platform with a
Flutter Android client, running on a single DigitalOcean VPS.

## Where I left off (end of session 2026-11-13)

**Branch:** `wip/mobile-api` at `1f5c279` (docs dedupe) — pushed to GitHub.
Working tree is clean. Nothing in-flight.

**Production (LIVE and VERIFIED):**
- VPS at `8a71f6b` (the last code commit before docs; docs commits don't
  affect the running app). Fully deployed and verified end to end.
- Migration `87cd66d8578c` applied (`Organization.vertical`). Unchanged
  since #45 (three sessions ago).
- Services active: `roman-sms.service`, `roman-worker.service`,
  `roman-panel.service` (restarted post-pull, all three `active`).
- Mobile API live at `https://romansms.com/api/v1/*` (unchanged since
  `6b07d67`, mobile-only commit; no new API endpoints since).
- **Full onboarding flow verified end to end** (2026-11-13): real signup
  → approval with vertical selection → welcome email + password-set link
  → login → first campaign sent → queued → complete → wallet debited.
  Test org cleaned up. No regressions.

**Flutter app:** Release APK from `6b07d67` on physical device. **Not
touched since 2026-11-01 (multiple sessions).** No verification since
`6b07d67` — worth a session to verify it still builds and connects
against the current API (mobile API contract hasn't changed but the User
model has gained `status`, `department`, and org has gained `vertical`).

**Database (prod):** Migrated to `87cd66d8578c`. Five orgs, four users.
Two real customers: Fitting (school, schedule #1 fires through
2026-11-29) and ORONEK (business, 0 contacts as of last check).

**Database (local):** Migrated to `87cd66d8578c`. Seeded with test
fixtures (org ids differ from prod; `tasms` is id 5 locally, id 4 in prod).

## What got done this arc (four sessions, 2026-11-10 → 2026-11-13)

Eight features shipped. All browser-verified or CLI-verified end to end.

| Feature | Migration | Tests | Notes |
|---|---|---|---|
| **A5** school-admin user CRUD | — | +18 | `/school/users` list, create, edit, delete, reset pw, dept dropdown |
| **docs/DEPARTMENTS.md** | — | — | Q1/Q2/Q3 workflow guide (the department contract) |
| **#49** last-run bug fix | — | +2 | Silent prod bug: schedule's last fire never happened |
| **#44** schedule pre-reservation | `c41928d919da` | +10 | Reserve at create, refund on cancel/overage/complete |
| **#46** user lifecycle | `e37cc1348332` | +8 | suspend (login OK, send blocked) / terminate (no login) / reactivate |
| **#45** Organization.vertical | `87cd66d8578c` | +6 | school / business / NULL, master-only |
| **#47** user detail page | — | +4 | `/school/users/<id>` with activity summary |
| **#16** schedules CRUD | — | +8 | Edit times/body/name/filters, delete if unfired, detail polish |

**Test progression: 189 → 247. +58 tests.**

**Prod is on `8a71f6b` with two real customers, both correctly classified
(Fitting=school, ORONEK=business), and both protected by the reservation
and lifecycle systems.**

**Critical backlog is empty.** Every remaining item is polish or
deferred-by-choice. No half-shipped features.

## What's next

Pick from (no blockers between them):

**(a) Flutter mobile app health check** — the app hasn't been touched in
multiple sessions. Verify it still builds, connects to the current API,
and works against the model changes (`User.status`, `User.department`,
`Organization.vertical`). **My recommendation** — highest value because
it's the only unverified surface.

**(b) #50 passwordless sudo for specific systemctl commands** — 5-min
win. Every deploy costs a sudo prompt. Add to `/etc/sudoers.d/`:
oyomthorm ALL=(ALL) NOPASSWD: /bin/systemctl restart roman-sms, /bin/systemctl restart roman-worker, /bin/systemctl restart roman-panel, /bin/systemctl is-active *

**(c) #38 user delete FK migration** — 4 NOT NULL FKs block user
deletion (chat_read_state, chat_message, notification_dismissal,
pool_permission.granted_by). No customer has asked; but if one does,
delete via `/school/users/<id>/delete` will fail. Add migration with
`ON DELETE CASCADE` on those four, `ON DELETE SET NULL` on the ten
nullable ones. ~1 session.

**(d) #39 RUNBOOK CLI verification note** — document the CLI verification
pattern used for #16 and A5 (state-transition scripts on prod via SSH,
not real browser clicks). ~1 hour.

**(e) #51 onboarding copy varies by vertical** — the #45 foundation
enables different welcome emails for school vs business. Currently both
get the same generic email. Nice UX; not urgent.

**(f) #32 pahappa_sync drift fix** — clicking "Sync to Pahappa" credits
the master wallet for the total balance difference, without provenance.
Deferred since before A1.

## Deferred / known issues (carry forward)

**From the mobile-only arc (still open):**
1. Panel grant form bug (500 entered → 10 saved).
2. Empty `recent_activity` renders zero-height Card on dashboard.
3. Dashboard "Hello, Admin" hardcoded in `dashboard_screen.dart`.
4. Dashboard header "Roman SMS • Verified" hardcoded.
5. Master org users hitting `/api/v1/dashboard` get master-org stats.
6. `withOpacity` deprecation: `contacts_screen.dart:171`, `chat_detail_screen.dart:99,134`.
7. Unused `go_router` import in `dashboard_screen.dart:1`.
8. Router churn — `routerProvider` recreates `GoRouter` on every auth state.
9. Password dialog error handling uses `contains('422')`.
10. `_refresh()` in `ContactDetailScreen` uses bare `catch (_)`.
11. `DELETE /contacts/<id>` is hard delete — no undo.
12. `update_contact` clear_group/clear_district untested with non-null.
13. Contacts endpoint error taxonomy inconsistent.
14. Campaign detail polish.
15. Contact detail district picker (no API round exists yet).
16. `iso()` emits naive datetimes without `Z` — cross-cutting.
17. `audit.log()` commits own transaction, swallows exceptions.
18. `svc.delete(group)` doesn't guard referenced `Schedule.group_id`.
19. `GET /groups/<id>` returns `contact_count: null` by design.
20. `CupertinoIcons` referenced but `cupertino_icons` not in pubspec.
21. `flutter_lints/flutter.yaml` include can't resolve.
22. Unused local `r` at `new_campaign_screen.dart:86`.
23. `contacts_screen.dart` name-empty fallback — pre-existing display bug.
24. `add_contact(None, ...)` raises `AttributeError` on `org.id`.
25. Test fixtures leak on mid-run crash — `test_groups_api.py` has no try/finally.
26. `contacts/form.html` phone field readonly by design — add hint.
27. Group detail actions icons — cosmetic polish.
28. `new_campaign_screen.dart` Radio groupValue/onChanged deprecation.

**From this arc:**
29. #50 passwordless sudo (5-min).
30. #38 user delete FK migration (see above).
31. #39 RUNBOOK CLI verification note.
32. #51 onboarding copy varies by vertical (deferred).
33. #32 pahappa_sync drift fix (deferred).
34. #43 self-service plan purchase (deferred).
35. Flutter mobile app health check (see (a) above).

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
   --short`. Any unexpected `??` file is a bug in the paste (often a
   `WriteAllText` on an unset or wrong-path variable). Delete and
   investigate.
5. **Test fixture tracing.** Trace mutations to the assertion point,
   not the function entry. `create_associate` needs `master_org`;
   `check_can_send` needs subscription + wallet. Fixtures must provide.
6. **A throw in a pasted line does not stop later lines.** The mutation
   must be the last line of the paste, or inside an `if/else` where the
   `else` contains the mutation. Refines prior working-style notes.
7. **Test first, commit second.** Never commit on the assumption that
   tests pass — run them, paste the exit code, then commit.
8. **Feature arc: inspect → design confirm → write paste → verify →
   browser/CLI verification → commit → deploy.**
9. **Verification vs. feature sessions are different.** Verification
   sessions produce confidence, not commits. Feature sessions produce
   commits. Both are valuable.
10. All prior working-style notes (1–52 in the previous statement) remain
    in force. See `docs/DECISIONS.md` and previous session logs for the
    full historical list.

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
  2026-11-29. **#49 fixed the silent last-run bug** — before this fix,
  the final message would have been silently lost.
- `tasms`: 166 contacts, wallet ~844 after onboarding test cleanup.
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
- **Currently at `8a71f6b` (app); docs commits don't deploy.**
- SSH key auth for `oyomthorm` — no password prompt on `ssh` (added
  this arc). `sudo` still prompts — use `ssh -t`.

**Backups:** `/srv/roman-sms/backups/` — daily cron at 03:00 UTC, schema
only. Pre-department rollback backup at
`/srv/roman-sms/backups/pre_department_2026_11_09.sql` (508 KB, verified
2026-11-09, contains 28 `CREATE TABLE` statements).

**SMTP:** Mailgun on port 2525 (DigitalOcean blocks 25/465/587 —
permanent platform policy). Domain `mg.romansms.com` verified via DNS
TXT records. Works end to end (verified during onboarding test).

## First action of next session

1. `cd D:\Dev_Apps\roman_sms`
2. `git fetch origin wip/mobile-api`
3. `git pull origin wip/mobile-api` — confirm at `1f5c279` (or later
   docs commit on top)
4. `git status --short` — expect clean
5. Confirm VPS is at `8a71f6b` and services active
6. Pick from (a) through (f) above

**Recommended: (a) Flutter mobile app health check.** The app hasn't been
touched in multiple sessions and hasn't been verified against the current
API (User now has status + department; Organization has vertical). One
session to confirm it still builds and connects.

**No migration pending. Deploy is standard (no DB changes for docs).**