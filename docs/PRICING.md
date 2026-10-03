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

## Retail tiers (current)

| Plan | Credits | Price (UGX) | Rate/SMS | Wholesale | Margin |
|---|---|---|---|---|---|
| Starter | 1,000 | 45,000 | 45 | 35 | 10 |
| Growth | 10,000 | 400,000 | 40 | 35 | 5 |
| Business | 50,000 | 1,750,000 | 35 | 30 | 5 |
| Scale | 200,000 | 6,000,000 | 30 | 25 | 5 |

Every tier's rate sits above the wholesale rate for that volume band.
The Starter tier carries the largest absolute margin and serves as an
entry point.

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