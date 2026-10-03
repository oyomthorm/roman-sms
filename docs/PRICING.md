# Pricing (internal)

Not shared with clients. This is the working model behind what they
see on the plans page.

## Cost structure

- **Wholesale cost per SMS from Pahappa:**
  - UGX 35 for 1 – 10,000
  - UGX 30 for 10,001 – 100,000
  - UGX 25 for 100,001 – 300,000
  - UGX 20 for 300,001 – 600,000
  - Contact sales for 600,000+
- **Segment multiplier.** Messages over 160 characters cost more per
  segment. Opt-out link adds roughly 60 characters. A 100-char body
  stays one segment; a 140-char body becomes two.
- **Failure rate buffer.** Assume 2–5% of sends fail and are refunded.
  Lost revenue but not lost wholesale — Pahappa does not bill failed
  sends.

## Retail tiers (current — after the 0.7.1 increase)

| Plan | Credits | Price (UGX) | Rate/SMS | Wholesale | Margin |
|---|---|---|---|---|---|
| Starter | 1,000 | 50,000 | 50 | 35 | 15 |
| Growth | 10,000 | 450,000 | 45 | 35 | 10 |
| Business | 50,000 | 2,000,000 | 40 | 30 | 10 |
| Scale | 200,000 | 7,000,000 | 35 | 25 | 10 |

Every tier's rate sits above the wholesale rate for that volume band.
The Starter tier carries the largest absolute margin and serves as an
entry point.

> **History.** The 0.7.1 release raised every tier by UGX 5 per SMS
> (Starter 45→50, Growth 40→45, Business 35→40, Scale 30→35) after two
> consecutive test sends came back at UGX 35 and UGX 20 wholesale. The
> 5 UGX buffer covers the worst-case wholesale rate on every tier.
> Applied via `scripts/update_prices_2026_10.py`. Invoices created
> before the change are unaffected — prices are snapshotted at invoice
> creation.

## Free credit grants

- **Signup welcome:** 100 credits. Configurable via
  `SIGNUP_STARTER_CREDITS`.
- **Pool permission grant:** 500 credits per quarter per contributing
  associate. Manual for now via `flask grant`.
- **Master opening balance:** 100,000 credits. Bookkeeping only —
  consumed only if the master sends.
- **Platform opening balance:** 100,000 credits to the system org.
  Consumed by pool campaigns.

## Fee structure not yet monetised

- **Registered sender IDs.** Phase 5. Setup fee covers registration
  cost plus margin; monthly fee covers renewal plus margin.
- **Custom campaigns.** If an associate asks for a bespoke integration
  (bulk import from their ERP, custom reports), quote by day.

## Pricing rules

- Never discount below cost. If a client negotiates hard, offer extra
  credits, not a lower price. The price per credit stays fixed.
- Never quote a plan price before the wholesale rate is confirmed.
- Review pricing quarterly. If wholesale cost changes, existing plans
  are grandfathered for the current subscription period but new plans
  reflect the new cost.

## Competitor notes

(Update as you learn.)

- EgoSMS direct: retail pricing published on their site.
- Other Ugandan resellers: check pricing before setting yours.