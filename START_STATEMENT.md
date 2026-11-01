# Roman SMS — session start statement

I'm continuing work on Roman SMS, a Flask SMS reseller platform with a
Flutter Android client, running on a single DigitalOcean VPS.

## Where I left off (end of session 2026-11-01, continued)

**Branch:** `wip/mobile-api` at `6b07d67` — pushed to GitHub.
Working tree is clean. Nothing is in-flight.

**Production (LIVE and VERIFIED):**
- VPS at `6b07d67` — same as local, fully deployed.
- Migration `6c7a338d1274` applied (`Contact.group_id NOT NULL`,
  `ContactImport.skipped_no_group`). Unchanged this round — `6b07d67`
  added no migration (mobile-only).
- Services active: `roman-sms.service`, `roman-worker.service`, `roman-panel.service`
  (restarted post-pull, all three `active`).
- Mobile API live at `https://romansms.com/api/v1/*` with the new contract.
- All 3 enforcement checks verified prod: POST without group → 422,
  PATCH with null group_id → 422, DELETE non-empty without move_to → 422.
- `GET /api/v1/groups/<id>/contacts` confirmed on prod: `401` unauth
  (route exists, auth-gated). Payload = `{group, contacts, stats}`; rows
  are `serializers.contact` (same shape as `/api/v1/contacts`), so
  tap-through works; `group.contact_count` and `stats.{total,opted_out}`
  are computed server-side.

**Flutter app:** Release APK built from `6b07d67` (52.1 MB) and installed
on physical device. Verified:
- (R6b, previous round) Add-contact sheet requires group; save disabled
  until picked; POST includes `group_id`; contact lands in correct group.
- (R7, this round) Group detail opens from Groups tab tap; header shows
  backend-computed Total / Opt-outs; contact rows list with tap-through to
  `ContactDetailScreen`; FAB opens AddContactSheet with the group
  **preselected**; sheet/detail return invalidates the group's own provider.
- Installed and confirmed working on device (no adb; installed by user).

**Database (prod):** Migrated to `6c7a338d1274`. 507 contacts, 0 NULL groups.
Associate account `associate@romansms.com` — **password `Temp2026!`** (confirmed
in prod by successful login this session; note: NOT `TempAssociate2026!`).

**Database (local):** Migrated. Seeded with test fixtures (see "Local test
fixtures" below).

## What got done this session (2026-11-01 continuation)

### Commit 3 (mobile) — `a3ffc2e`

**AddContactSheet** now requires a group before submission:
- `int? _selectedGroupId` state.
- `ref.watch(groupsProvider)` drives a `DropdownButtonFormField<int>`.
- Save disabled when no group selected / groups loading / groups errored.
- POST body includes `group_id`.
- Empty-group state shows "No groups exist yet. Create a group first."
- `value:` → `initialValue:` (Flutter 3.33+ deprecation fix).

**GroupPickerDialog:**
- Removed the "None (remove from group)" ListTile + Divider. Clearing a
  contact's group is no longer legal under the invariant.
- Docstring updated.

**contact_detail_screen.dart:**
- Stale comment updated (`// null clears, int sets` → `// group_id always non-null now`).

**Cleanup:**
- Deleted duplicate `mobile/lib/screens/add_contact_sheet.dart` (untracked,
  identical logic, different formatting; `contacts_screen.dart` imports
  `../widgets/add_contact_sheet.dart`).

### Deploy (this session)

**Sequence executed:**

1. Local pre-check: HEAD == origin == `a3ffc2e`, clean tree.
2. VPS pre-check: `daac71b`, migration `00404835aeb7`, service active.
3. `git pull origin wip/mobile-api` → `a3ffc2e` (fast-forward, 24 files changed).
4. `flask db upgrade` → applied `6c7a338d1274`.
5. **`sudo systemctl restart` — first attempt failed (`sudo` needs TTY).**
   Retried with `ssh -t` and `sudo bash -c '...'` — worked, both services active.
6. Backend verification: unauth 401, authenticated round-trip on `/groups/3`,
   all 3 contract checks (422s) pass on prod.
7. `flutter clean && flutter pub get && flutter build apk --release` → 52 MB APK.
8. `flutter install --release` → device. Add-contact-sheet verified working.
9. Web smoke test — all steps pass (group detail actions, import-to-group,
   add-contact-from-group).

**Critical window** (migration applied, old APK on device) was ~3 minutes.
Restart-services step unblocked by re-run with `ssh -t`.

### R7 — mobile group detail screen (`6b07d67`)

**New `mobile/lib/screens/group_detail_screen.dart`:**
- Fetches `/api/v1/groups/<id>/contacts` via a new
  `groupContactsProvider` (`FutureProvider.autoDispose.family`, returns
  the **whole map** — mirrors `campaignDetailProvider`, not the
  `['items']` list-unwrap).
- Header: group name (from payload `group.name`, fallback
  `initialGroupName`, then `Group #<id>`), two stat circles using
  `stats.total` / `stats.opted_out` (backend-computed — not recounted
  client-side).
- Rows: `contacts_screen.dart`-identical `ListTile` (avatar, name/phone,
  opted-out pill or chevron), tap → `Navigator.push` → `ContactDetailScreen`
  (same `MaterialPageRoute` pattern, not `context.push`).
- FAB → `showModalBottomSheet(AddContactSheet(initialGroupId: groupId))`.
- Decision **B**: screen invalidates `groupContactsProvider(groupId)`
  after sheet return **and** after detail return — the sheet keeps its
  own `contactsProvider` invalidation only; no coupling added.

**`AddContactSheet`:** added `final int? initialGroupId`, seeded
`_selectedGroupId` in `initState` (widget is `ConsumerStatefulWidget`,
so field-init can't read `widget.`). Dropdown, `canSubmit` gate
(`groupsAsync.hasValue`), and `_submit` body unchanged — preselection
does **not** bypass the loading/errored guard.

**`router.dart`:** `/groups/:id` inside `ShellRoute` (shell/nav stays
visible), right after `/groups`. Mirrors `/campaigns/:id`'s
`int.parse(state.pathParameters['id']!)`. Reads `initialGroupName` from
`state.extra as String?` (null on deep link — screen falls back to
payload name).

**`groups_screen.dart`:** replaced the "No chevron, no onTap — R6b adds
group detail" placeholder comment with `onTap: () => context.push(
'/groups/${group['id']}', extra: group['name'])` + trailing
`Icon(Icons.chevron_right)`. Added `package:go_router/go_router.dart`
import.

**`providers.dart`:** appended `groupContactsProvider` after the last
provider. `flutter analyze` clean of new warnings (10 issues, all
pre-existing: #6, #7, #24, #25, #31).

**Deploy:** pull `a3ffc2e..6b07d67` (FF, 6 files — includes `d4fe631`
docs commit the VPS had not yet seen), restart 3 services, `401` on the
new route, rebuild APK, install, device-verified. **No migration.**

## What's next

The R6b/R7 mobile rounds are done. Deferred list below is the backlog;
pick from it in the next session.

**Recommended short first: #14 SMTP configuration (~20 min).**
Unblocks signup end-to-end. Small, self-contained, high leverage.

**Recommended big next: #16 Schedules CRUD** (own session — biggest
remaining round).

Everything else on the deferred list is polish or small fixes; none
blocks the other.

## Deferred / known issues (accumulated)

**Still open from before this session:**
1. Panel grant form bug (500 entered → 10 saved).
2. Empty `recent_activity` renders zero-height Card on dashboard.
3. Dashboard "Hello, Admin" hardcoded in `dashboard_screen.dart`.
4. Dashboard header "Roman SMS • Verified" hardcoded.
5. Master org users hitting `/api/v1/dashboard` get master-org stats.
6. `withOpacity` deprecation: `contacts_screen.dart:171`,
   `chat_detail_screen.dart:99,134` (new code uses `withValues`).
7. Unused `go_router` import in `dashboard_screen.dart:1`.
8. Router churn — `routerProvider` recreates `GoRouter` on every auth state.
9. Password dialog error handling uses `contains('422')`.
10. `_refresh()` in `ContactDetailScreen` uses bare `catch (_)`.
11. `DELETE /contacts/<id>` is hard delete — no undo.
12. `update_contact` clear_group/clear_district untested with non-null.
13. Contacts endpoint error taxonomy inconsistent.
14. SMTP configuration (~20 min, unblocks signup end-to-end).
15. Invoices endpoint (`Invoice` model exists in `app/models/wallet.py`).
16. Schedules CRUD (biggest round, own session).
17. Campaign detail polish.
18. Contact detail **district** picker (no API round exists yet).
19. **`iso()` emits naive datetimes without `Z`** — cross-cutting serializer
    decision, own round.
20. **`audit.log()`** commits own transaction, swallows exceptions.
21. **`svc.delete(group)` doesn't guard referenced `Schedule.group_id`.**
22. **`GET /groups/<id>` returns `contact_count: null` by design.**
23. **`CupertinoIcons` referenced but `cupertino_icons` not in pubspec.**
24. **`flutter_lints/flutter.yaml` include can't resolve.**
25. **Unused local `r`** at `new_campaign_screen.dart:86`.
26. **`contacts_screen.dart` name-empty fallback** — pre-existing display bug.
27. **`add_contact(None, ...)`** raises `AttributeError` on `org.id` before
    reaching group guard.
28. **Test fixtures leak on mid-run crash** — `test_groups_api.py` has no
    try/finally cleanup.
29. **`contacts/form.html` phone field is readonly by design** — add hint
    under the field ("Phone cannot be changed; delete and re-create to
    update it").
30. **Group detail actions icons** — currently text labels in web panel;
    icon swap is cosmetic polish.
31. **`new_campaign_screen.dart` Radio groupValue/onChanged deprecation**
    (Flutter 3.32+).

## Working style that works

1. **Inspect before writing.** Never serialize a field or call a service from memory.
2. **Small chunks for large edits.** 5–10 line `Add-Content` calls, verify
   after each. Or editor paste for full-file replacements.
3. **Precondition checks before destructive actions.**
4. **One commit per logical unit.**
5. **Verify the actual thing, not a proxy.**
6. **Stop when the state is clean.**
7. **Answer the precondition question before destructive actions.**
8. **`git add` paths are relative to cwd.** Copy from `git status --short`.
9. **Diff-stat before diff-content on unexpected commits.**
10. **Silent-catch code paths produce false-positive tests.**
11. **PowerShell 5.x `Set-Content -Encoding UTF8` writes a BOM.** Use
    `[System.IO.File]::WriteAllText` with `UTF8Encoding $false`.
12. **Not every dev env has every user.**
13. **Deploy verification sequence:**
    - `git rev-parse --short HEAD` → `git fetch` → `git rev-parse --short origin/branch`
      → pull → restart → unauth check → authenticated round-trip.
    - Extended for migrations: after `db upgrade`, verify `db current` == new head.
14. **PowerShell variables don't survive shell restarts.**
15. **Don't use placeholder tokens in pasteable commands.**
16. **Check the actual screen under test, not the neighboring screen.**
17. **A navigation change must not orphan a just-shipped feature.**
18. **`if (...) { return }` at paste top-level does not halt subsequent
    pasted lines — the guard must contain the mutation.**
19. **An anchor string must be verified unique by `[regex]::Matches(...).Count`
    before use. Never infer uniqueness from a truncated grep.**
20. **Git's `warning: CRLF will be replaced by LF` describes the index, not
    the worktree.** Confirm endings with `[regex]::Matches($text, "`r`n").Count`.
21. **The verifier itself can be wrong.** `-SimpleMatch` disables regex.
    Regex mode for anything with escapes. Trace expected counts by
    `Select-String` first, don't estimate.
22. **Test-fixture choice must trace all mutations up to the assertion point.**
23. **A failed test run leaves DB state** — clean up before re-run.
24. **`flask shell -c` doesn't exist.** Use `python -c "..."` with app context.
25. **Multi-line paste starting with `ssh` loses everything after `ssh`
    to the password prompt.** Split, or configure key auth.
26. **Fetch before push, not just before deploy.**
27. **Amend-after-push requires `--force-with-lease`.**
28. **`git push` non-fast-forward rejection is the safety net.**
29. **Verification output is not source-of-truth by itself.**
30. **A `Replace`-based write block is not idempotent.** After running,
    `git diff` in the same block.
31. **Tests should not depend on incidental state of shared fixtures.**
32. **`git diff --stat` excludes untracked files.**
33. **Verify sanity counts by `Select-String` before writing.** Do not
    estimate from memory.
34. **Master admin (org 1) is empty in local DB.**
35. **Python scripts embedded in PowerShell `python -c "..."` blocks break on
    escaped quotes (`\"`).** Use a temp file with single-quoted here-string.
36. **Local DB and prod DB are separate with different fixture coverage.**
37. **Before re-running a write block, `Select-String` for target content.**
38. **Commit messages with `<` or `>` can fail under `git commit -m`.**
    Use `-F <file>` for safety.
39. **When anchoring on a template line, the anchor must end where the line
    continues.** Do not append `\n` unless the target truly ends the line.
40. **Flutter files can be duplicated across `screens/` and `widgets/`.**
    Enumerate with `Get-ChildItem -Recurse -Filter '<name>.dart'` and check
    imports before editing. `contacts_screen.dart` imports reveal the
    canonical path.
41. **`flutter analyze` reports by file path — a warning on
    `screens/X.dart` when you edited `widgets/X.dart` means either two files
    exist or you edited the wrong one.**
42. **Deleting an untracked file doesn't show in `git status` as `D`** —
    it's a local filesystem event only. Commit messages describing it should
    note "(was untracked)".
43. **Pre-existing BOMs in source files can be stripped by
    `WriteAllText` without one.** Net improvement but **appears as an
    unintended line change** in the diff. Note it when it happens; it's fine.
44. **`sudo systemctl` over non-interactive ssh fails with "a terminal is
    required."** Use `ssh -t` and/or wrap in `sudo bash -c '...'` for one
    prompt. Plain `ssh "sudo ..."` will silently fail.
45. **`<<EOF` heredocs are bash-only.** In PowerShell, `git commit -F - <<'EOF'`
    fails at parse time and the message body executes as commands. Use
    `@'...'@` + `[System.IO.File]::WriteAllText($msgPath, $msg, UTF8Encoding($false))`
    + `git commit -F $msgPath`. Refines #35/#38.
46. **A `throw` in a pasted line does not stop later lines in the same paste.**
    The lines are independent statements; a `throw` is a notification, not a
    guard. The only reliable guard is the mutation being the final line of the
    paste, with nothing after it. Refines #18.
47. **Mojibake in the *display* of a source file may be a real Unicode char
    on disk.** `Get-Content` renders `—` as `â€”`; `ReadAllText` sees U+2014.
    Anchor `Replace` on ASCII-only prefixes, and locate the line with
    `.Contains()` — do not match the full byte string. Refines #21/#30.
48. **`Resolve-Path` fails on a file that doesn't exist yet.** For
    `WriteAllText` of a new file, use `Join-Path (Get-Location) $file`.
49. **Escape Dart `$` in PowerShell strings with a backtick:**
    `` '/groups/`${group['id']}' `` — without it, PowerShell eats the variable
    and writes `'/groups/',`. Refines #15/#16.
50. **Never apply a "corrected" transformation to a file whose prior
    transformation is not verified restored.** `git status --short` must be
    empty before re-applying. A line-count check is not enough — you can be
    at the wrong count for the right reason. Refines #37.
51. **A literal-URL grep missing is not proof an endpoint is absent.** Flask
    composes the URL from `url_prefix` + decorator; a route registered
    `@bp.get("/<int:id>/contacts")` never contains the contiguous string
    `groups/<id>/contacts`. Grep decorators and `url_prefix`, then confirm
    the composed path. Refines #21/#30.
52. **For a file under ~500 lines, whole-file replacement via one here-string
    + one `WriteAllText` as the final line is strictly safer than line-index
    surgery.** Index arithmetic's failure modes (partial apply, silent no-op,
    post-write re-execution) all vanish. The diff is larger; the failure
    surface is not. Refines #2.

## Test accounts

- **Master admin:** `admin@romansms.local` / `ChangeMe123!` (seed default).
- **Associate:** `associate@romansms.com` / **`Temp2026!`**
  - **Prod:** org `TempAssoc` (id 4, slug `tasms`). Full name "Temp Associate Test".
  - **Local:** org `tasms` (id 5). Full name "Temp Associate Test".

**Change passwords before production customers.**

## Local test fixtures

**Local DB (different org ids from prod — `tasms` is id 5, not 4):**

- Users: `admin@romansms.local` (org 1, `ChangeMe123!`),
  `admin@test.com` (org 1), `oyomthorm.21@gmail.com` (org 3),
  `associate@romansms.com` (org 5, `TempAssociate2026!` — **local uses
  `TempAssociate2026!`, prod uses `Temp2026!`**).
- Orgs: `roman-sms` (1), `roman-platform` (2), `roman-computer-services` (3),
  `tasms` (5).
- Group: `Franco Intro` (id 25, in `tasms`) with 1 contact.
- Contact: `256700000001` "Test Contact A" (id 14, in group 25).

**Prod DB (production state):**

- Orgs: `Roman SMS` (1, master), `Roman SMS Platform` (2), `Fitting` (3),
  `TempAssoc` (4, slug `tasms`).
- **`Franco Intro`** in prod is **id 3**, has **172 contacts**.
- Associate user in prod org 4, password `Temp2026!`.

## Deployment state

**VPS:** DigitalOcean droplet `ubuntu-s5-2vcpu-4gb-30gb-mkc1`,
`165.245.199.37`. Ubuntu 24.04. Postgres 16.
- App at `/srv/roman-sms/`, user `oyomthorm`.
- systemd: `roman-sms.service` (gunicorn, 3 workers, `127.0.0.1:8000`),
  `roman-worker.service`, `roman-panel.service` (Flask panel on `127.0.0.1:8080`).
- Nginx + Let's Encrypt SSL on `https://romansms.com`.
- **Currently at `6b07d67` — fully deployed and verified.** The VPS will be
  one `docs:` commit behind after this statement update; that is expected and
  benign (docs don't deploy).

**Backups:** `/srv/roman-sms/backups/` — daily cron at 03:00 UTC, schema only.
Ad-hoc `pg_dump` needs `chown postgres` first.

## First action of next session

1. `cd D:\Dev_Apps\roman_sms`
2. `git fetch origin wip/mobile-api`
3. `git pull origin wip/mobile-api` — confirm at `6b07d67` (plus the `docs:`
   statement commit on top)
4. `git status --short` — expect clean
5. Confirm VPS is at `6b07d67` and services active
6. Update this statement if needed, commit as `docs:`

Then **#14 SMTP configuration** (~20 min): configure SMTP, unblock signup
end-to-end. After that, **#16 Schedules CRUD** (own session).

**No migration pending. Deploy is standard (no DB changes).**