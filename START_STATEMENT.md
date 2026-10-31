# Roman SMS — session start statement

I'm continuing work on Roman SMS, a Flask SMS reseller platform with a
Flutter Android client, running on a single DigitalOcean VPS.

## Where I left off (end of session 2026-10-31)

**Branch:** `wip/mobile-api` at commit `1de2130` — pushed to GitHub.
Working tree is clean. Nothing is in-flight.

**Production:** Mobile API live at `https://romansms.com/api/v1/*`.
VPS backend is at `daac71b` (groups CRUD). Rounds 5b and R6a were
Flutter-only and correctly **not** deployed. Service active, 3 workers,
`127.0.0.1:8000`.

**Flutter app:** Release APK built from `1de2130`, installed on the
physical Android device, tested against production. 5b picker and R6a
Groups tab both verified on device.

**Database:** Clean, migrated, seeded. Four orgs:
- `Roman SMS` (id 1, master)
- `Roman SMS Platform` (id 2)
- `Fitting` (id 3)
- `TempAssoc` (id 4, slug `tasms`) — associate test org

**Test data present:** TempAssoc has one group `"Franco Intro"` with
1 contact. Decide next session whether to keep as a fixture or clean up.

## What got done this session (2026-10-31)

### Round 5a — Groups CRUD API (`daac71b`)
- New `app/api/v1/groups.py`: list, create, get, patch, delete
  (`?move_to=<id>` optional). Wraps existing `app/services/groups.py`.
- `serializers.group(g, contact_count=None)` added.
- Registered in `app/api/v1/__init__.py` (imports + `_CHILDREN`).
- `scripts/test_groups_api.py`: 19 assertions, all pass locally
  (`python -m scripts.test_groups_api` — note the `-m`; running
  `python scripts/foo.py` fails on `sys.path`).
- Prod verified: 401 unauth, full authenticated round-trip (create/
  get/delete) with associate account.

### Round 5b — Group picker on contact detail (`9b0f4da`)
- `groupsProvider` added to `mobile/lib/state/providers.dart`.
- New `mobile/lib/widgets/group_picker_dialog.dart` — reusable
  `ConsumerWidget` with `show(context, {currentGroupId})`, returns
  `({bool picked, int? groupId})` record. Designed for reuse by the
  campaign round (placeholder at `new_campaign_screen.dart:201`).
- `contact_detail_screen.dart` edits:
  - `_groupId` **promoted from getter to state** so picker PATCH updates
    the tile.
  - `_refresh()` now sets `_groupId` (fixes stale read when group changes
    elsewhere).
  - Group tile: tappable, chevron, shows group **name** (falls back to
    `Group #id` if provider not loaded), PATCHes `group_id`, invalidates
    `contactsProvider`.
  - `_districtId` left as getter with comment — same staleness bug,
    deferred to a district round.
- Device-verified on prod: assign, reassign, clear, cold-restart
  persistence. Web panel agrees in both directions.

### Round 6a — Groups tab replaces Contacts (`1de2130`)
- New `mobile/lib/screens/groups_screen.dart`: single stat circle
  (total groups), "All Groups" list with per-group `contact_count`.
  **Tap is no-op** — group detail deferred to R6b.
- `router.dart`: added `/groups`; **kept `/contacts`** (contact detail
  and picker remain reachable).
- `app_shell.dart`: nav index 2 → Groups (`/groups`, group icon);
  title mapping for `/groups`; **Contacts added to drawer** as escape
  hatch (without it, R6a orphaned the just-shipped 5b picker — check 6
  failed, fixed before commit).
- No FAB on Groups screen. Contacts screen and `/contacts` unchanged.

## What's next — Round 6b (group detail)

**This is the next round.** Own inspection first, then one commit
pair (backend + Flutter). Estimated ~2.5h.

**Scope:**
- Backend: `GET /api/v1/groups/<id>/contacts` wrapping
  `svc.contacts_in(org, group_id)`. Decide response shape:
  `{group, contacts, stats:{total, opted_out}}` **or** return contacts
  only and let Flutter compute counts. **Inspect `add_contact_sheet.dart`
  first** — still unseen this session; it determines whether
  add-contact-within-group needs changes.
- Flutter: group detail screen (total contacts, opt-outs, contact list,
  add-contact button, tap-through to `ContactDetailScreen`).
- Decide whether drawer "Contacts" entry stays as "All contacts" or is
  removed now that group detail is the primary path.

**Not starting until inspected.** No code without seeing
`add_contact_sheet.dart` and deciding the stats response shape.

## Deferred / known issues (accumulated, not this round)

**From 2026-10-30 (still open):**
1. Panel grant form bug (500 entered → 10 saved).
2. Empty `recent_activity` renders zero-height Card on dashboard.
3. Dashboard "Hello, Admin" hardcoded in `dashboard_screen.dart`.
4. Dashboard header "Roman SMS • Verified" hardcoded.
5. Master org users hitting `/api/v1/dashboard` get master-org stats.
6. `withOpacity` deprecation: `contacts_screen.dart:171`,
   `chat_detail_screen.dart:99,134` (new code uses `withValues`).
7. Unused `go_router` import in `dashboard_screen.dart:1`.
8. Router churn — `routerProvider` recreates `GoRouter` on every
   `authState` change.
9. Password dialog error handling uses `contains('422')`.
10. `_refresh()` in `ContactDetailScreen` uses bare `catch (_)`.
11. `DELETE /contacts/<id>` is hard delete — no undo.
12. `update_contact` clear_group/clear_district untested with non-null.
13. Contacts endpoint error taxonomy inconsistent (`create()` throws
    422 for all failures).

**From prior sessions:**
- SMTP configuration (~20 min, unblocks signup end-to-end)
- Invoices endpoint (`Invoice` model exists in `app/models/wallet.py`)
- Schedules CRUD (biggest round, own session)
- Campaign detail polish
- Contact detail **district** picker (no API round exists yet)

**New from 2026-10-31:**
- **`iso()` emits naive datetimes without `Z`** — Flutter can't reliably
  parse as UTC. Affects contacts/campaigns/groups. Cross-cutting
  serializer decision, own round.
- **`audit.log()`** commits its own transaction, swallows exceptions —
  audit is best-effort, not transactional with the mutation. Design
  choice, document rather than change.
- **`svc.delete(group)` doesn't guard referenced `Schedule.group_id`** —
  deleting a group leaves schedules pointing at a missing group. Web
  panel has same behavior; mobile now exposes it.
- **`GET /groups/<id>` returns `contact_count: null` by design** — list
  endpoint is the count source. Documented.
- **`CupertinoIcons` referenced but `cupertino_icons` not in pubspec** —
  build warning; Cupertino icons may render blank in release.
- **`flutter_lints/flutter.yaml` include can't resolve** —
  `flutter_lints` not in pubspec deps.
- **Unused local `r`** at `new_campaign_screen.dart:86`.
- **`contacts_screen.dart` has format-only churn** — suggests editor
  format-on-save is active. Future "3 files changed" assumptions may be
  wrong; always read `git status --short` first.

## Test accounts

- **Master admin:** `admin@romansms.local` / `ChangeMe123!` (seed default)
- **Associate:** `associate@romansms.com` / **`Temp2026!` was the value
  mid-session, then `invalid_credentials`.** Current value unknown.
  Statement's `TempAssociate2026!` is stale. Needs reset or confirmed
  value before next session's testing.
  - Belongs to org `TempAssoc` (id 4, slug `tasms`).
  - `full_name = "Temp Associate Test"`.

**Change passwords before production customers.**

## Deployment state

**VPS:** DigitalOcean droplet `ubuntu-s5-2vcpu-4gb-30gb-mkc1`,
`165.245.199.37`. Ubuntu 24.04. Postgres 16.
- App at `/srv/roman-sms/`, user `oyomthorm`.
- systemd: `roman-sms.service` (gunicorn, 3 workers, `127.0.0.1:8000`),
  `roman-worker.service`, `roman-panel.service` (Flask panel on
  `127.0.0.1:8080`).
- Nginx + Let's Encrypt SSL on `https://romansms.com`.

**Backups:** `/srv/roman-sms/backups/` — daily cron at 03:00 UTC,
schema only. Ad-hoc `pg_dump` needs `chown postgres` first.

## Working style that works

1. **Inspect before writing.** Never serialize a field or call a service
   from memory — that's the class of bug ADR-019 documents (and the
   `serializers.user()` bug fixed 2026-10-30).
2. **Small chunks for large edits.** 5–10 line `Add-Content` calls,
   verify after each. Or editor paste for full-file replacements.
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
   `git status --short` output. (Hit twice this session — once from
   repo root with `mobile/` missing, once from `mobile/` with
   `mobile/` prefixed. Copy from status output and it can't fail.)
9. **Diff-stat before diff-content on unexpected commits.** Format churn
   is common.
10. **Silent-catch code paths produce false-positive tests.** When a new
    path swallows errors, deploy the dependency before testing, and test
    for a *visible transition*, not just a plausible end state.
11. **PowerShell 5.x `Set-Content -Encoding UTF8` writes a BOM.** Breaks
    Python and JSON. Use `Out-File -Encoding ascii` for curl bodies,
    `[System.IO.File]::WriteAllText` with `UTF8Encoding $false`, or
    editor paste.
12. **Not every dev env has every user.** Prod has users that local
    doesn't and vice versa.
13. **Deploy verification sequence:** `git rev-parse --short HEAD`
    (precondition) → `git fetch` → `git rev-parse --short origin/branch`
    (verify what origin has **before** pulling) → pull → restart →
    unauthenticated endpoint check (401 not 404 proves route registered)
    → authenticated round-trip. Skipping the origin-check step caused a
    404-vs-401 false diagnosis this session.
14. **PowerShell variables don't survive shell restarts.** Multi-step
    diagnostics that depend on `$token` across separate pastes will fail
    with `invalid_credentials`/`unauthorized` cascades. Use a single
    self-contained block that logs in at the top, and print any values
    needed for the next block at the end.
15. **Don't use placeholder tokens in pasteable commands.** `<EMAIL>`,
    `<PASSWORD>`, `<contact-id>` will be pasted literally. Use `export`
    + `$VAR` or an all-in-one block that derives them.
16. **Check the actual screen under test, not the neighboring screen.**
    "Group tile not active" turned out to be the Contacts-list stat
    circle, not the detail-screen Group tile. Ask "which screen" when a
    UI symptom is reported.
17. **A navigation change must not orphan a just-shipped feature.**
    R6a replaced the Contacts tab and stranded the 5b picker; caught by
    check 6 (feature reachability), fixed with a drawer entry before
    commit. Add "can the user still reach X?" to every nav round's
    verification list.

## First action of next session

1. `cd D:\Dev_Apps\roman_sms`
2. `git fetch origin wip/mobile-api`
3. `git pull origin wip/mobile-api` — confirm at `1de2130`
4. `git status --short` — expect clean
5. Confirm VPS backend is still `daac71b` (should be — no deploy since)
6. **Resolve the associate password** before any prod testing
7. Paste the outputs.

Then pick a target. **Recommended: R6b (group detail).** Start with
inspection only:

Get-Content mobile/lib/widgets/add_contact_sheet.dart
Get-Content app/api/v1/contacts.py | Select-Object -First 30

and decide the group-detail stats response shape before writing.

## What I need from the assistant

- Same discipline: inspect, one round, verify on device, commit clean,
  push.
- When something fails, isolate the layer before changing code.
- Flag when a step is skipped.
- Honest scope estimates.
- If a command I provide relies on shell state from a previous paste,
  provide it as one self-contained block with save-points printed.
- If a symptom is reported from an ambiguous screen, ask which screen
  before diagnosing.