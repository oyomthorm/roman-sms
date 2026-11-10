# Backlog

Every "Not in v1" feature lives here with the person who asked for it
and a cost estimate. Anything untouched for 3 months gets deleted.

Format: `Feature — requested by NAME (DATE) — est. Nd — notes`

## Parking lot

- [ ] Passwordless sudo for specific systemctl commands (#50) — internal, est. 0.1d
- [ ] User delete FK migration (#38) — needed only if a customer asks to remove a user with chat/pool history — est. 0.5d
- [ ] RUNBOOK: CLI verification note (#39) — document the state-transition test pattern — est. 0.5d
- [ ] Onboarding copy varies by vertical (#51) — school vs business welcome emails — est. 0.5d
- [ ] pahappa_sync drift fix (#32) — external top-ups conflated with consumption drift — est. 1d
- [ ] Self-service plan purchase (#43) — deferred until 20+ schools — est. 3d
- [ ] Flutter mobile app health check — verify build + API compat against the current model — est. 0.5d

- [ ] Passwordless sudo for specific systemctl commands (#50) — internal, est. 0.1d
- [ ] User delete FK migration (#38) — needed only if a customer asks to remove a user with chat/pool history — est. 0.5d
- [ ] RUNBOOK: CLI verification note (#39) — document the state-transition test pattern — est. 0.5d
- [ ] Onboarding copy varies by vertical (#51) — school vs business welcome emails — est. 0.5d
- [ ] pahappa_sync drift fix (#32) — external top-ups conflated with consumption drift — est. 1d
- [ ] Self-service plan purchase (#43) — deferred until 20+ schools — est. 3d
- [ ] Flutter mobile app health check — verify build + API compat against the current model — est. 0.5d

- [ ] Per-associate sub-users UI — (not yet requested) — est. 3d
- [ ] Automated payment gateway — (not yet requested) — est. 5d
- [ ] Public API for associates — (not yet requested) — est. 4d
- [ ] Registered sender IDs per associate — (gated on paying client) — est. 2d + cost of registration
- [ ] Two-factor authentication — (not yet requested) — est. 2d

## Ideas considered and parked

- **Referral program.** Associates refer other businesses, get free
  credits. Deferred until 5 paying associates exist.
- **District-based auto-groups.** Auto-create a group per district from
  imported contacts. Deferred — the district filter already covers this
  use case.
- **Campaign preview simulator.** Show a rendered message on a phone
  mockup before sending. Nice-to-have, not blocking.
- **CAPTCHA on signup.** Only add if spam arrives. Honeypot plus rate
  limit is the current defence.
- **Top-up reminder emails.** Warn associates before their balance
  hits the low-balance threshold, based on their 30-day burn rate.
  Deferred until a real associate asks for it.
- ## Shipped (no longer parked)

- **Scheduled campaigns.** Shipped in `0.8.0`. See `CHANGELOG.md` and
  ADR-003 for `CampaignSchedule`, `services/schedules.py`, and the
  worker scheduler pass.
- **Character / segment / cost counter.** Shipped in `0.8.1`. See
  ADR-013.
- **Paste-numbers recipient source.** Shipped in `0.8.1`. See ADR-014.
- **Invoice PDF export.** Shipped in `0.9.0`.
- **Campaign completion emails.** Shipped in `0.9.0`.
- **Dashboard usage charts.** Shipped in `0.9.0`.

## Deleted (untouched for 3+ months)

(Nothing here yet. First cleanup review: 2026-01-01.)

## Shipped this arc (2026-11-10 → 2026-11-13)

See `CHANGELOG.md` and `START_STATEMENT.md` for full detail.

- **A5 — School-admin user CRUD.** `/school/users` list, create, edit,
  delete, reset password, department assignment. Master no longer creates
  school users (deliberate — see Q1 in `DEPARTMENTS.md`). +18 tests.
- **A5 — docs/DEPARTMENTS.md.** Q1/Q2/Q3 workflow guide; the contract
  for who-manages-whom, who-pays, when-credits-are-debited.
- **#49 — Last-run schedule bug.** Silent prod bug: every schedule's
  last `scheduled_times` entry was skipped because `claim_due_schedule`
  marked the schedule `completed` before `materialize_run` could fire
  it. Caught by reproduction test, fixed, deployed. +2 tests.
- **#44 — Schedule pre-reservation.** Reserve at create, refund on
  cancel / overage / completion, edit recalculates. See ADR-023. +10 tests.
- **#46 — User lifecycle.** Suspend / terminate / reactivate. See
  ADR-024. +8 tests.
- **#45 — Organization.vertical.** School / business / NULL, master-only.
  See ADR-025. +6 tests.
- **#47 — User detail page.** `/school/users/<id>` with activity summary
  (campaigns, schedules, audit log). +4 tests.
- **#16 — Schedules CRUD.** Edit times / body / name / filters with
  automatic reservation adjustment; delete only if unfired. See
  ADR-023 (edit-as-refund-and-redebit). +8 tests.

**#33 — Personalized campaign sends.** Shipped before this arc (2026-11-09).
CSV upload + `{{column}}` template merge. `services/personalization.py`,
`renderer.render_personalized`, `routes/campaigns.py::personalized_new`
and `personalized_preview`. See prior session logs.
