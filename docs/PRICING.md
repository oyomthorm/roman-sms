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
  segment. A 100-char body stays one segment; a 140-char body becomes
  two.
- **Failure rate buffer.** Assume 2–5% of sends fail and are refunded.
  Lost revenue but not lost wholesale — Pahappa does not bill failed
  sends.

## Retail tiers (current — October 2026)

| Plan | Bundle | Advertised band | Rate/SMS | Price (UGX) | Wholesale | Margin |
|---|---|---|---|---|---|---|
| Starter | 1,000 | 1 – 10,000 | 45 | 45,000 | 35 | 10 |
| Growth | 10,000 | 10,001 – 100,000 | 40 | 400,000 | 30 | 10 |
| Business | 100,000 | 100,001 – 300,000 | 35 | 3,500,000 | 25 | 10 |
| Scale | 300,000 | 300,001 – 600,000 | 30 | 9,000,000 | 20 | 10 |
| Enterprise | quoted | 600,000+ | quoted | quoted | quoted | quoted |

Every published tier earns a **flat UGX 10 margin per SMS**. This is a
change from the prior schedule, where Starter carried 15 and the other
tiers carried 10.

Each plan advertises a volume band (matching Pahappa's wholesale bands),
but the plan itself is a fixed bundle at the lower edge of the band.
Buying more than the advertised band requires a custom quote via the
master (Enterprise).

**Enterprise (600,000+):** no fixed plan. The master quotes manually.
The pricing page does not show an Enterprise tier.

**Credits never expire.** A plan is a one-time purchase. Credits land
in the append-only wallet and remain usable indefinitely. There is no
monthly subscription cycle. The internal `validity_days` field is set
to `36500` (100 years) as a perpetual sentinel; the display layer
renders "No expiry" for anything >= that value.

> **History.** The 0.7.1 release (Oct 2026) raised every tier by UGX 5
> per SMS after two consecutive test sends came back at UGX 35 and
> UGX 20 wholesale. The October 2026 revision reverses that increase
> and takes a flat 10 UGX margin on every tier, aligning each tier's
> retail rate to its wholesale band. Applied via
> `scripts/update_prices_2026_10.py`. Old plan rows are deactivated,
> not edited. Invoices created before the change are unaffected —
> prices are snapshotted at invoice creation.

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
- To change prices again, write a new dated script following the
  pattern in `scripts/update_prices_2026_10.py`. Never edit a live
  plan's price directly — always deactivate and insert.

## Competitor notes

(Update as you learn.)

- EgoSMS direct: retail pricing published on their site.
- Other Ugandan resellers: check pricing before setting yours.