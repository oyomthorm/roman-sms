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
- [ ] Personalized campaign sends (CSV + `{{col}}` template merge) — requested by schools vertical (2026-11-08) — est. 3–4d — see "Ideas considered and parked" below

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
- **Personalized campaign sends.** Schools (and later SACCOs, pharmacies,
  landlords) need per-recipient messages: fee reminders with pupil name,
  parent name, fee balance, due date, and bursar contact; meeting
  reminders with parent name, meeting time, and headteacher contact.
  Current campaign pipeline sends **one** body to all recipients — no
  merge fields, no per-row substitution, no per-row segment accounting,
  so a 100-pupil fee reminder cannot include each pupil's balance today.
  Feature shape: CSV upload + `{{column}}` template syntax; per-row
  rendered body stored on `MessageLog` (schema change); wallet debit
  computed as **sum of per-row segments** (not rows x template segments),
  because substitution changes length; worker dispatch sends per-recipient
  body. Optional `{{payment_ussd}}` merge variable so schools can embed a
  mobile-money USSD line (per-row CSV column, or per-org default with a
  per-campaign override — decide at build time). Web-only first; mobile
  deferred. Est. 3-4d. Blocks nothing. See `SCOPE.md` change rule:
  named requester = schools vertical; written reason = above; cost = 3-4d.

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