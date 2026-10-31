# Roman SMS — session start statement

I'm continuing work on Roman SMS, a Flask SMS reseller platform with a
Flutter Android client, running on a single DigitalOcean VPS.

## Where I left off (end of session 2026-11-01 ~01:00 EAT)

**Branch:** `wip/mobile-api` at `fd9778a` — pushed to GitHub.
Working tree is clean. Nothing is in-flight.

**Production:** VPS backend at `daac71b` — **4 commits and 1 migration behind
local.** Migration `6c7a338d1274` (Contact.group_id NOT NULL, ContactImport.
skipped_no_group) applied **locally only**, not on VPS. Mobile API live at
`https://romansms.com/api/v1/*` but with the OLD contract (contacts can still
be created without a group). Service active, 3 workers, `127.0.0.1:8000`.

**Flutter app:** Release APK installed on physical Android device is from
`1de2130` — **breaks under the new invariant if VPS migration runs before
APK is rebuilt.** Deploy sequence must be atomic: pull → migrate → rebuild
APK → install → verify, in one window.

**Database (local):** Migrated to `6c7a338d1274` (head). Seeded with test
fixtures this session (see "Local test fixtures" below). Prod DB untouched.

## What got done this session (2026-10-31 → 2026-11-01)

### R6b backend — `GET /groups/<id>/contacts` (`da73778`)
- Nested endpoint returning `{group, contacts, stats:{total, opted_out}}`.
- Wraps `svc.contacts_in`; computes `opted_out` server-side.
- +4 assertions in `test_groups_api.py` (unauth 401, populated group,
  empty group, nonexistent 404). Cross-org 404 not separately asserted —
  `svc.get` filters by org_id and returns None identically.
- Not deployed to VPS (part of round group below).

### Backend invariant — contacts belong to a group (`581eabf`)
- **Model:** `Contact.group_id` → `nullable=False`. `ContactImport.
  skipped_no_group` Integer counter.
- **Migration:** `6c7a338d1274_contacts_require_group_import_skipped_.py`
  (auto-generated, applied locally, **NOT applied on VPS**).
- **Service `add_contact`:** requires `group` or `group_id`; raises
  `ContactError('Group is required.')`.
- **Service `import_csv`:** rows with no resolvable group skipped as
  `ContactImportIssue(status='skipped_no_group')`; counter incremented.
- **Service `groups.delete`:** raises `GroupError('Cannot delete a non-empty
  group without specifying where to move contacts.')` when contacts exist
  and `move_to_group_id` not supplied. Empty groups delete directly.
- **API contract (via existing try/except handlers):**
  - `POST /contacts` missing group_id → 422 invalid_contact.
  - `PATCH /contacts/<id>` `{group_id: null}` → 422 invalid_update
    (previously set clear_group=True; now rejected).
  - `DELETE /groups/<id>` non-empty without move_to → 422 delete_failed.
- **Template:** `contacts/import_report.html` gained `skipped_no_group` chip
  (amber) and counter in skipped-total sum.
- **Tests:** step 12 rewritten (422 + delete-after-move), step 13 rewritten
  (contact now in gid2), assertion 22 uses fresh empty group, +2 new
  assertions (POST without group, PATCH group_id:null). ALL PASS.

### Web group detail actions + import-to-group (`e0c8723`)
- **`groups/detail.html`:** per-contact Actions column — Edit (link) /
  Opt-out (POST, hidden if opted out) / Delete (POST). All confirm-dialoged.
  CSRF tokens in both POST forms (was missing → 400 on POST initially).
- **Referrer redirect:** `contacts.edit`, `contacts.delete`, `contacts.optout`
  use `request.referrer` when same-origin, else fall back to `contacts.index`.
  Preserves context when triggered from group detail.
- **`contacts/form.html`:** removed `<option value="">No group</option>`.
- **`routes/contacts.py::edit`:** rejects empty group with "Group is required."
  flash + re-render. Previously `clear_group=True` → IntegrityError under
  NOT NULL schema (latent bug activated by migration).
- **Import-to-group:** new `GET+POST /groups/<gid>/import` route in
  `routes/groups.py`. Reuses `svc.import_csv(default_group=group.name)`.
  `contacts/import.html` gains `preset_group` context — form action switches
  to the new endpoint, group field becomes read-only display, green banner.
  "Import" button added to group detail header.
- **`groups/delete.html`:** `<select name="move_to" required>` with
  disabled+selected placeholder, "No group" option removed (illegal).
- **`contacts/import.html` hint:** "Leave blank if your file has a group
  column" + "Rows with no group column and no default group will be skipped."
  (was "Blank = use file column" — no longer accurate).

### Web add-contact-from-group (`fd9778a`)
- **`routes/contacts.py::new`:** reads `?group_id=<id>` → `preselected_group_id`
  to template. Uses referrer redirect on success (was `contacts.index`).
- **`contacts/form.html`:** group `<option>` marked `selected` when
  `contact.group_id == g.id` (edit path) OR `preselected_group_id == g.id`
  (new-from-group path).
- **`groups/detail.html`:** "Add contact" button in header (between Import
  and Delete, secondary outline with plus icon) + empty-state "Add a contact"
  link. Both to `/contacts/new?group_id=<gid>`.

## What's next — Commit 3 (mobile), then deploy

### Commit 3 — mobile: require group on AddContactSheet

**Files to inspect first:**
- `mobile/lib/widgets/add_contact_sheet.dart` (75 lines, seen earlier).
- `mobile/lib/widgets/group_picker_dialog.dart` (need to see Clear path).
- `mobile/lib/state/providers.dart` (groupsProvider shape).
- `mobile/lib/screens/contacts_screen.dart:36` (only callsite of AddContactSheet).

**Design (decided this session):**
- `AddContactSheet` gets an in-sheet group dropdown (required). Uses
  `groupsProvider` to populate. POST body includes `'group_id': _selectedGroupId`.
  Submit disabled until a group is chosen.
- `group_picker_dialog.dart` — remove the "Clear" option (contact group is
  now required, clearing is illegal per invariant).
- No other Dart changes — the pre-existing `AddContactSheet()` call from
  `contacts_screen.dart` still compiles (sheet itself gains the field).

**Estimate:** ~45–60 min including `flutter analyze` (compile check).
**Do NOT rebuild APK yet** — that's part of the atomic deploy step.

### Deploy — atomic sequence (~45–90 min, one continuous window)

**Precondition:** VPS at `daac71b`, local at `fd9778a` (or newer after commit 3).

**Rule #13 sequence, extended for the migration:**

1. VPS: `git rev-parse --short HEAD` (expect `daac71b`).
2. VPS: `git fetch origin wip/mobile-api && git rev-parse --short origin/wip/mobile-api` (expect `fd9778a` or newer).
3. VPS: `git pull origin wip/mobile-api`.
4. VPS: `source venv/bin/activate && python -m flask --app app db current` (expect `00404835aeb7`).
5. VPS: `python -m flask --app app db upgrade` (runs migration `6c7a338d1274`).
   **CRITICAL:** at this moment, old APK 400s on POST /contacts. **Do NOT
   leave the VPS in this state overnight.** Follow immediately with steps 6–9.
6. VPS: `sudo systemctl restart roman-sms.service roman-worker.service`.
7. VPS: unauth check — `curl -o /dev/null -w "%{http_code}" https://romansms.com/api/v1/groups/1/contacts` → **401** (route registered).
8. VPS: authenticated round-trip with associate account (login → GET /groups → GET /groups/<id>/contacts → 200 with stats).
9. **Local: rebuild APK** from `wip/mobile-api` — `flutter build apk --release`.
10. **Install APK on physical device.**
11. **Device test:** open app → Add contact sheet → confirm group dropdown required → pick group → save → verify contact lands in that group.
12. **Web smoke test in prod browser:** group detail actions work, import-to-group works, add-contact-from-group preselection works.

**Verification before declaring deploy complete:**

- Prod migration at `6c7a338d1274` (via `flask db current`).
- Old test contacts still load, new test contact created via mobile lands in correct group.
- All 3 API endpoints behave per new contract (POST without group → 422, PATCH group_id:null → 422, DELETE non-empty without move_to → 422).

## Local test fixtures (added this session)

**Local DB (different from prod):**

- **Users:**
  - `admin@romansms.local` — org `roman-sms` (id 1), password `ChangeMe123!` (seed default). Master admin.
  - `admin@test.com` — org `roman-sms` (id 1).
  - `oyomthorm.21@gmail.com` — org `roman-computer-services` (id 3).
  - `associate@romansms.com` — org `tasms` (id 5), password `TempAssociate2026!`. **Created this session for browser tests.**
- **Orgs:** `roman-sms` (1), `roman-platform` (2), `roman-computer-services` (3), `tasms` (5). Note **id 4 does not exist locally** — org numbering diverged from prod.
- **Group:** `Franco Intro` (id 25, in `tasms`) with 1 contact.
- **Contact:** `256700000001` "Test Contact A" (id 14, in group 25).

**Prod DB (unchanged, production state):**

- Orgs: `Roman SMS` (1, master), `Roman SMS Platform` (2), `Fitting` (3), `TempAssoc` (4, slug `tasms`).
- **`associate@romansms.com`** exists in prod (org 4) — password reset to `TempAssociate2026!` earlier in this session (via `flask shell` on VPS).
- **`Franco Intro`** exists in prod (org 4) with 1+ contacts.
- 335 prod contacts in org 3, 172 in org 4.

**Master admin:** `admin@romansms.local` / `ChangeMe123!` (seed default).
**All test passwords should be changed before production customers.**

## Deferred / known issues (accumulated)

**From sessions before 2026-10-30 (still open):**
1. Panel grant form bug (500 entered → 10 saved).
2. Empty `recent_activity` renders zero-height Card on dashboard.
3. Dashboard "Hello, Admin" hardcoded in `dashboard_screen.dart`.
4. Dashboard header "Roman SMS • Verified" hardcoded.
5. Master org users hitting `/api/v1/dashboard` get master-org stats.
6. `withOpacity` deprecation: `contacts_screen.dart:171`,
   `chat_detail_screen.dart:99,134`.
7. Unused `go_router` import in `dashboard_screen.dart:1`.
8. Router churn — `routerProvider` recreates `GoRouter` on every `authState`.
9. Password dialog error handling uses `contains('422')`.
10. `_refresh()` in `ContactDetailScreen` uses bare `catch (_)`.
11. `DELETE /contacts/<id>` is hard delete — no undo.
12. `update_contact` clear_group/clear_district untested with non-null.
13. Contacts endpoint error taxonomy inconsistent (create throws 422 for all).

**From 2026-10-30 / 2026-10-31 sessions:**
- SMTP configuration (~20 min, unblocks signup end-to-end).
- Invoices endpoint (`Invoice` model exists in `app/models/wallet.py`).
- Schedules CRUD (biggest round, own session).
- Campaign detail polish.
- Contact detail **district** picker (no API round exists yet).
- **`iso()` emits naive datetimes without `Z`** — Flutter can't reliably
  parse as UTC. Cross-cutting serializer decision, own round.
- **`audit.log()`** commits own transaction, swallows exceptions. Best-effort.
- **`svc.delete(group)` doesn't guard referenced `Schedule.group_id`.**
- **`GET /groups/<id>` returns `contact_count: null` by design** — list
  endpoint is the count source. Documented.
- **`CupertinoIcons` referenced but `cupertino_icons` not in pubspec.**
- **`flutter_lints/flutter.yaml` include can't resolve.**
- **Unused local `r`** at `new_campaign_screen.dart:86`.
- **`contacts_screen.dart` name-empty fallback** — `contact['name'] ?? 'Unknown Name'`
  never fires for empty string (backend returns `""` not null). Pre-existing
  display bug, deferred.
- **`contacts_screen.dart` format churn** — editor format-on-save active.
  Always `git status --short` first.
- **`add_contact(None, ...)`** raises `AttributeError` on `org.id` before
  reaching group guard. Not a caller path in prod, noted for future caller
  safety.
- **Test fixtures leak on mid-run crash.** `test_groups_api.py` doesn't use
  try/finally. Add in a future test-hardening pass.
- **`contacts/form.html` phone field is readonly by design.** Add a hint
  under the field ("Phone cannot be changed; delete and re-create to update
  it"). Not done — cosmetic polish.
- **Edit-form phone editability** would require API validation + cascade
  updates to campaigns/opt-outs/message_log. Own round.
- **`groups/detail.html` per-contact actions** use text labels (Edit / Opt-out
  / Delete), not icons. Icon swap is cosmetic polish, own commit if wanted.
- **Test-account `TempAssoc` password reset on VPS** — value `TempAssociate2026!`.
  Change before production customers.

## Working style that works

1. **Inspect before writing.** Never serialize a field or call a service
   from memory.
2. **Small chunks for large edits.** 5–10 line `Add-Content` calls, verify
   after each. Or editor paste for full-file replacements.
3. **Precondition checks before destructive actions.** Prod mutations
   need confirmation. "I don't know" is an answer.
4. **One commit per logical unit.** `feat(api):`, `feat(mobile):`,
   `fix(api):`, `docs:`. Never `git add .`.
5. **Verify the actual thing, not a proxy.** Curl the live endpoint.
   Install the APK on the real phone. Read the actual DB row.
6. **Stop when the state is clean.** Pushed branch, clean tree, no
   half-applied changes.
7. **Answer the precondition question before destructive actions.**
8. **`git add` paths are relative to cwd, not repo root.** Copy from
   `git status --short` output.
9. **Diff-stat before diff-content on unexpected commits.**
10. **Silent-catch code paths produce false-positive tests.**
11. **PowerShell 5.x `Set-Content -Encoding UTF8` writes a BOM.** Use
    `[System.IO.File]::WriteAllText` with `UTF8Encoding $false`.
12. **Not every dev env has every user.**
13. **Deploy verification sequence:** `git rev-parse --short HEAD` →
    `git fetch` → `git rev-parse --short origin/branch` → pull → restart →
    unauth endpoint check (401 not 404) → authenticated round-trip.
14. **PowerShell variables don't survive shell restarts.**
15. **Don't use placeholder tokens in pasteable commands.** `<EMAIL>`,
    `<PASSWORD>` will be pasted literally.
16. **Check the actual screen under test, not the neighboring screen.**
17. **A navigation change must not orphan a just-shipped feature.**
18. **`if (...) { return }` at paste top-level does not halt subsequent
    pasted lines — the guard must contain the mutation.**
19. **An anchor string must be verified unique by `[regex]::Matches(...).Count`
    before use. Never infer uniqueness from a truncated grep.**
20. **Git's `warning: CRLF will be replaced by LF` describes the index, not
    the worktree.** Confirm endings with `[regex]::Matches($text, "`r`n").Count`.
21. **The verifier itself can be wrong.** `-SimpleMatch` disables regex —
    `\(` matches literal backslash-paren. Use regex mode for anything with
    escapes. Also — before asserting expected counts, trace every occurrence
    by `Select-String` — do not estimate from memory.
22. **Test-fixture choice must trace all mutations up to the assertion
    point,** not just the ones relevant to the endpoint under test.
23. **A failed test run leaves DB state** — clean up before re-run.
24. **`flask shell -c` doesn't exist.** Use `python -c "..."` with app context.
25. **Multi-line paste starting with `ssh` loses everything after `ssh`
    to the password prompt.** Split, or configure key auth.
26. **Fetch before push, not just before deploy.**
27. **Amend-after-push requires `--force-with-lease`** after confirming
    `git diff origin/branch HEAD` is empty and the origin tip is your own.
28. **`git push` non-fast-forward rejection is the safety net working.**
    Inspect, classify, act — never `--force` first.
29. **Verification output is not source-of-truth by itself.** Empty
    `git diff` is stronger than a runtime `print`.
30. **A `Replace`-based write block is not idempotent.** After running,
    `git diff` in the same block and treat that as sole source of truth.
31. **Tests should not depend on incidental state of shared fixtures.** If
    a test mutates a fixture, every downstream assertion on that fixture
    must remain valid, or use an isolated fixture.
32. **`git diff --stat` excludes untracked files.** `git add` first, then
    `git diff --cached --stat` for full picture.
33. **Verify sanity counts by `Select-String` before writing.** Do not
    estimate from memory.
34. **Master admin (org 1) is empty in local DB.** For local UI testing
    of org-scoped features, use the associate account.
35. **Python scripts embedded in PowerShell `python -c "..."` blocks break
    on escaped quotes (`\"`).** Use a temp file (`@'...'@` single-quoted
    here-string) + `python $tmp` + `Remove-Item`.
36. **Local DB and prod DB are separate with different fixture coverage.**
    Seed local with a temp script (idempotent, checks existence first).
37. **Before re-running a write block, `Select-String` for target content.**
    If already present, skip — the block is stale.
38. **Commit messages with `<` or `>` can fail under `git commit -m`**
    in PowerShell when `<` is at a word boundary. Use `-F <file>` for
    safety with multi-line messages.
39. **When anchoring on a template line, the anchor must end where the line
    continues.** Do not append `\n` unless the target truly ends the line.

## Test accounts

- **Master admin:** `admin@romansms.local` / `ChangeMe123!` (seed default).
- **Associate:** `associate@romansms.com` / `TempAssociate2026!` (reset this
  session on both local and VPS).
  - **Local:** org `tasms` (id 5). Full name "Temp Associate Test".
  - **Prod:** org `TempAssoc` (id 4, slug `tasms`).

**Change passwords before production customers.**

## Deployment state

**VPS:** DigitalOcean droplet `ubuntu-s5-2vcpu-4gb-30gb-mkc1`,
`165.245.199.37`. Ubuntu 24.04. Postgres 16.
- App at `/srv/roman-sms/`, user `oyomthorm`.
- systemd: `roman-sms.service` (gunicorn, 3 workers, `127.0.0.1:8000`),
  `roman-worker.service`, `roman-panel.service` (Flask panel on `127.0.0.1:8080`).
- Nginx + Let's Encrypt SSL on `https://romansms.com`.
- **Currently at `daac71b` — 4 commits behind. Migration `6c7a338d1274`
  NOT applied. Deploy is the first task next session.**

**Backups:** `/srv/roman-sms/backups/` — daily cron at 03:00 UTC, schema only.
Ad-hoc `pg_dump` needs `chown postgres` first.

## First action of next session

1. `cd D:\Dev_Apps\roman_sms`
2. `git fetch origin wip/mobile-api`
3. `git pull origin wip/mobile-api` — confirm at `fd9778a`
4. `git status --short` — expect clean
5. Confirm VPS is still `daac71b` and `roman-sms.service` active
6. Update this statement, commit as `docs:`

Then **commit 3 (mobile)** — inspect `add_contact_sheet.dart`,
`group_picker_dialog.dart`, `providers.dart`, `contacts_screen.dart:36`.
Apply changes, `flutter analyze`, commit, push.

**Then deploy** — the atomic sequence (pull → migrate → restart → verify
backend → rebuild APK → install → device test) — as one continuous window.
**Do not split the migration from the APK deploy.**