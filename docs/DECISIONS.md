# Architecture Decision Records

One page per decision. Add a new ADR for anything expensive to reverse.

---

## ADR-018 — Every credit must have a source

**Date:** 2026-10-06 · **Status:** Accepted

**Context.** The wallet ledger is append-only, but nothing stopped a
service from writing a positive delta that came from nowhere. Every
`flask grant`, every `mark_paid`, every subscription grant, every
starter credit silently created new credits in the internal ledger.
The invariant

    SUM(all wallet deltas) == credits held on the platform

held only by accident, and only because nobody had granted anything
yet. As soon as one associate received 500 credits, the sum would
have overstated reality by 500.

**Decision.** `wallet_svc.credit()` now requires either an explicit
`source_org_id` or a reason from `EXTERNAL_CREDIT_REASONS`. When a
source is given, the source wallet is debited in the same
transaction, and the credit row records `source_org_id` for audit.

The whitelist of legitimate external sources:

- `master_opening_balance` — seed time, mirrors Pahappa
- `master_topup` — manual top-up from Pahappa
- `pahappa_sync` — reconciliation with the live Pahappa balance
- `refund` — reversal of a failed send
- `adjustment` — dev / test correction

Every other internal movement goes through `transfer(from, to, ...)`
or `credit(..., source_org_id=...)`.

`scripts/reconcile.py` verifies the invariant: every credit that
isn't tagged as external must have `source_org_id` set, and that
org must have a matching debit with the same reference.

**Consequences.**
- Cannot accidentally invent credits. A call site that tries raises
  `WalletError` at the moment of the call, not silently weeks later.
- Ledger is auditable: any credit's lineage is one hop away.
- Requires `source_org_id` on `WalletTransaction` — a new column,
  part of the baseline migration.
- Refunds are the one exception, but they are reversals, not new
  credits, and the whitelist makes that explicit.
- `pahappa_sync` remains the mechanism for reconciling the master
  wallet with Pahappa, and it too is whitelisted.

---

## ADR-017 — Opt-out link removed from outbound messages

**Date:** 2026-10-03 · **Status:** Accepted

**Context.** Every message previously carried a trailing
`Opt out: <url>` line, appended by `services.renderer.append_optout`.
The link was the platform's only opt-out channel (ADR-004) because the
shared Pahappa sender ID does not support inbound SMS and there is no
shortcode for reply-STOP.

The link cost the associate real money — roughly 76 characters, enough
to push a short message from one segment into two. It also read as
spam-adjacent to recipients receiving a personal-seeming message with
an unfamiliar compliance footer.

**Decision.** Remove the automatic opt-out link. `render()` now
produces only `prefix + body`.

The `OptOut` table, platform-wide enforcement, the public landing page
at `/opt-out`, the token-based `/opt-out/<token>` route, and manual
opt-out marking by associates all remain. No message carries a token
anymore, but the code that would issue one still exists.

**Consequences.**
- Message cost drops for short messages that would have tipped into
  a second segment.
- Opt-outs are now the associate's responsibility. The associate
  agreement (see `ONBOARDING.md`) is the sole basis for consent.
- Compliance with Uganda's Data Protection and Privacy Act 2019
  shifts entirely to the associate's own practices. The platform no
  longer provides a per-message opt-out channel.
- If a client or regulator requires a per-message opt-out, a
  replacement is needed: a registered sender ID with reply-STOP
  support, or a per-associate opt-out link.

---

## ADR-016 — Server-side SVG charts, no JS library

**Date:** 2026-10-03 · **Status:** Accepted

**Context.** The dashboard needed usage charts. Chart.js and similar
libraries add 200 KB+ to every dashboard render, require a CDN or a
bundled asset, and bring their own upgrade treadmill. The data being
visualised is small and static per render.

**Decision.** All dashboard charts are rendered server-side as inline
SVG using Jinja templating. Bar heights, donut dashes, and progress
widths are computed in the template from the route's data.

**Consequences.**
- Zero JS dependencies, no external requests, no CDN to trust.
- Charts degrade gracefully — visible in any browser, no JS required.
- Visual language is limited to what SVG primitives support. No
  animations beyond CSS transitions on existing elements.
- Adding a new chart means writing Jinja, not JavaScript.

---

## ADR-013 — Character counter counts the brand prefix

**Date:** 2026-10-02 · **Status:** Accepted

**Context.** The new-campaign form needs a live character counter so
the associate knows whether the message will be one SMS or two. EgoSMS
counts raw body characters. That is wrong for a reseller: every message
we send goes out as `BRAND: body`, and Pahappa bills the whole thing.

A 150-character body with a 13-character prefix is 163 characters
delivered — two segments — but EgoSMS would show it as one. The
associate would be quoted one price and charged for two.

**Decision.** The client-side counter computes
`len(org.prefix + body)`, matches the segment arithmetic from
`services.renderer.segments`, and shows the shilling cost using the
org's current rate. It is a mirror of the server rule, not a
replacement for it. The server remains authoritative.

**Consequences.**
- The counter can drift from the server if the prefix or rate changes
  without a page reload. Acceptable: the server's `create_campaign`
  still computes the real cost and the wallet debit is correct.
- Associates see the true cost before submitting, which reduces
  refund disputes and support calls.
- A 20-character prefix materially changes the segment count for short
  messages. The counter makes this visible.

---

## ADR-014 — Paste-numbers recipient source on the campaign form

**Date:** 2026-10-02 · **Status:** Accepted

**Context.** Associates sometimes want to send a one-off message to a
small list of people who are not worth adding to the contact database —
a supplier list, a single event invite list, a test send. The current
form requires them to import the numbers as contacts first, then send
and optionally delete them.

**Decision.** Add a "Paste numbers" recipient source on the campaign
form. The associate pastes up to 500 numbers, one per line. The route
parses each with `services.phones.normalize_ug`, deduplicates, and
skips numbers on the platform-wide `OptOut` list. The numbers are used
for this campaign only; no `Contact` rows are created.

**Consequences.**
- Associates get a fast path for one-off sends without polluting
  their contact database.
- The 500 cap prevents the feature from being used as a bulk-import
  bypass. If someone wants to send to 10,000 numbers, they must import
  them, which means they appear in the contact database, which means
  the platform's opt-out and analytics logic applies.
- Numbers pasted here are not visible in `/contacts`. If the associate
  wants a record, they import instead.
- No `Contact` row means no group membership, no district, no
  long-term analytics. That is the point.

---

## ADR-015 — Schedule fields always visible on the form

**Date:** 2026-10-02 · **Status:** Accepted

**Context.** The new-campaign form has two modes: send now and
schedule. Hiding the schedule fields when "Send now" is selected keeps
the form short, but it also hides the existence of the feature. An
associate who has never used scheduling does not know it is available.

**Decision.** Show the schedule fields always. When "Send now" is
selected, apply `opacity-40` and `pointer-events-none` to dim and
disable them. When "Schedule" is selected, remove both classes.

**Consequences.**
- Scheduling is discoverable without clicking the Schedule radio.
- The form is longer. On mobile this is a bigger scroll.
- Pointer events are disabled when dimmed, so accidental clicks cannot
  toggle a day checkbox while the form is in send-now mode.
- The visual state and the logical state always agree because both are
  driven by the same CSS classes.

---

## ADR-001 — Append-only wallet ledger

**Date:** 2026-10-01 · **Status:** Accepted

**Context.** Credit balance must survive concurrency and disputes. A
mutable `credits` integer on `Organization` would race under concurrent
campaign creation and leave no audit trail.

**Decision.** Every credit and debit is a new `WalletTransaction` row
with a signed delta. Balance is derived by summing rows; each row caches
`balance_after` for O(1) reads. Writes take a `FOR UPDATE` lock on the
org row before reading the balance.

**Consequences.**
- Correct under concurrency when backed by Postgres.
- Full audit trail. Corrections are new rows, never edits.
- Reconcile job asserts `SUM(delta) == last.balance_after`.
- Postgres required in production; SQLite cannot provide the lock.

---

## ADR-002 — Master sender ID with body prefix

**Date:** 2026-10-01 · **Status:** Accepted

**Context.** Pahappa does not allow self-service registration of
multiple sender IDs. The reseller path exists but is too expensive for
a starter.

**Decision.** One master sender ID for the whole platform. Associates
get a per-brand body prefix, capped at 20 characters.

**Consequences.**
- Shared sender reputation; opt-out enforcement is critical.
- Message cost may include extra segments for the prefix.
- A single abusive associate can affect every other associate.
  Mitigated by rate limits, opt-outs, and the master kill switch
  (suspend).

---

## ADR-003 — Database-backed queue (no Celery)

**Date:** 2026-10-01 · **Status:** Accepted

**Context.** Celery + Redis add two services to operate. At launch
scale they are not justified.

**Decision.** `send_queue` table plus a Python worker using
`FOR UPDATE SKIP LOCKED`.

**Consequences.**
- Postgres required in production.
- Migration to Celery, if it ever happens, is a rewrite of the claim
  loop only — not the schema, not the send logic.
- Job recovery (requeue stuck jobs) is our responsibility;
  `requeue_stuck` handles it.

---

## ADR-004 — Outbound only

**Date:** 2026-10-01 · **Status:** Superseded by ADR-017

**Context.** Master sender ID does not support inbound SMS. Customers
cannot reply STOP to a shortcode because there is no shortcode.

**Decision.** Opt-outs are handled by the customer clicking a link in
the message body. Signed tokens with 6-month expiry. Platform-wide
`OptOut` table enforced across every org.

**Consequences.**
- Every message carries an opt-out URL when `PUBLIC_BASE_URL` is set.
- Segment count includes the URL, so cost is accurate.
- Compliance depends on the associate sending the URL; the associate
  agreement makes correct opt-out handling a condition of service.

---

## ADR-005 — Three roles, no permission tables

**Date:** 2026-10-01 · **Status:** Accepted

**Context.** Permission systems are scope creep for v1.

**Decision.** `master_admin`, `associate_admin`, `associate_user`.
Enforcement: route decorator + query scoping + service guard.

**Consequences.**
- Adding a fourth role later is a matrix row and a decorator, not a
  subsystem.
- The three enforcement layers mean no single mistake produces a data
  leak.

---

## ADR-006 — System org separate from master org

**Date:** 2026-10-02 · **Status:** Accepted

**Context.** The master org was doing two jobs: running the platform
and sending pool campaigns. Both used the same wallet.

**Decision.** Add `Organization.is_system`. A separate org
("Roman SMS Platform") is the sending identity for pool campaigns.

**Consequences.**
- Ledgers cleanly separate: master wallet = operating; system wallet =
  sending.
- Every list query must filter `is_system=False` where the system org
  should not appear.

---

## ADR-007 — Permission-gated master contact pool

**Date:** 2026-10-02 · **Status:** Accepted

**Context.** Reaching associate customers requires explicit permission.

**Decision.** Associates opt in via Settings. Agreement text is
snapshotted. Contacts copy into `PoolContact`. Revocation deletes those
rows.

**Consequences.**
- Legally defensible. Every grant carries its own agreement text.
- Opt-out propagates to the pool from every entry point.
- Grant is optional; refusing costs nothing.

---

## ADR-008 — Computed notifications with per-user dismissal

**Date:** 2026-10-02 · **Status:** Accepted

**Context.** Notifications must not become a stale inbox.

**Decision.** Notifications are computed on every render.
`NotificationDismissal` records "this user has dismissed this specific
condition". Keys include changing values.

**Consequences.**
- No stale notifications, ever.
- No cleanup job; the table grows slowly.

---

## ADR-009 — Delivery status via webhook, not polling

**Date:** 2026-10-02 · **Status:** Accepted

**Context.** Pahappa offers a webhook; polling is also possible.

**Decision.** Use the webhook. Store `provider_ref` on every
`MessageLog` row. Match on `(MsgFollowUpUniqueCode, number)`.

**Consequences.**
- No polling loop, no cron job.
- Endpoint must be secured by an unguessable token in the URL.
- Missed webhooks leave the row as `sent`, not `delivered`.

---

## ADR-010 — Gated self-signup

**Date:** 2026-10-02 · **Status:** Accepted

**Context.** Associates must apply without a call, but instant
activation is unsafe with a shared sender ID.

**Decision.** Public signup form creates a `SignupRequest`, not an
Organization. Master approves before provisioning.

**Consequences.**
- Every new tenant is approved by a human.
- Signup can be disabled at any time via `SIGNUP_ENABLED=0`.

---

## ADR-011 — Persistent import reporting

**Date:** 2026-10-02 · **Status:** Accepted

**Context.** Silent drops from a CSV import leave the associate unable
to know what went wrong.

**Decision.** Every import creates a `ContactImport` job plus one
`ContactImportIssue` per skipped row. Report page with downloadable
error CSV.

**Consequences.**
- Imports are auditable months later.
- Associates fix bad rows themselves.

---

## ADR-012 — Snapshot group name on pool contacts

**Date:** 2026-10-02 · **Status:** Accepted

**Context.** The pool needs a group filter without joining back to the
source Contact.

**Decision.** Snapshot `group_name` onto `PoolContact` at contribution
time.

**Consequences.**
- Filter is an indexed lookup, no join.
- History is honest: the pool reflects the group at grant time.
- Adding a group after granting requires a backfill or a re-grant.