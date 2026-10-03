# Backlog

Every "Not in v1" feature lives here with the person who asked for it
and a cost estimate. Anything untouched for 3 months gets deleted.

Format: `Feature — requested by NAME (DATE) — est. Nd — notes`

## Parking lot

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

## Shipped (no longer parked)

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