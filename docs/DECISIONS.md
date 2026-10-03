# Architecture Decision Records

One page per decision. Add a new ADR for anything expensive to reverse.

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

**Date:** 2026-10-01 · **Status:** Accepted

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

**Date:** 2026-10-08 · **Status:** Accepted

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

**Date:** 2026-10-08 · **Status:** Accepted

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

**Date:** 2026-10-08 · **Status:** Accepted

**Context.** Notifications must not become a stale inbox.

**Decision.** Notifications are computed on every render.
`NotificationDismissal` records "this user has dismissed this specific
condition". Keys include changing values.

**Consequences.**
- No stale notifications, ever.
- No cleanup job; the table grows slowly.

---

## ADR-009 — Delivery status via webhook, not polling

**Date:** 2026-10-08 · **Status:** Accepted

**Context.** Pahappa offers a webhook; polling is also possible.

**Decision.** Use the webhook. Store `provider_ref` on every
`MessageLog` row. Match on `(MsgFollowUpUniqueCode, number)`.

**Consequences.**
- No polling loop, no cron job.
- Endpoint must be secured by an unguessable token in the URL.
- Missed webhooks leave the row as `sent`, not `delivered`.

---

## ADR-010 — Gated self-signup

**Date:** 2026-10-08 · **Status:** Accepted

**Context.** Associates must apply without a call, but instant
activation is unsafe with a shared sender ID.

**Decision.** Public signup form creates a `SignupRequest`, not an
Organization. Master approves before provisioning.

**Consequences.**
- Every new tenant is approved by a human.
- Signup can be disabled at any time via `SIGNUP_ENABLED=0`.

---

## ADR-011 — Persistent import reporting

**Date:** 2026-10-08 · **Status:** Accepted

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

**Date:** 2026-10-08 · **Status:** Accepted

**Context.** The pool needs a group filter without joining back to the
source Contact.

**Decision.** Snapshot `group_name` onto `PoolContact` at contribution
time.

**Consequences.**
- Filter is an indexed lookup, no join.
- History is honest: the pool reflects the group at grant time.
- Adding a group after granting requires a backfill or a re-grant.