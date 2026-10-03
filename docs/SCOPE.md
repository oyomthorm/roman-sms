# Scope

Three lists. Every feature request goes into exactly one.

## In v1

**Platform**
- Master admin login, master console (overview, associates, signups,
  invoices, plans, master pool, platform sender, audit log)
- Create associate org + admin user from the browser
- Gated self-signup: applicant submits, master approves
- Suspend / activate associate
- Grant credits, assign plan, issue invoice, mark paid, reset passwords

**Associate**
- Login, dashboard, profile, settings
- Contacts: manual add, CSV import with preview and persistent report,
  export, opt-out, district filter
- Groups: create, rename, delete with reassign
- Templates: create, edit, delete
- Campaigns: build with group + district filter, one-off paste list,
  or all contacts; live character / segment / cost counter; send now
  or schedule; view delivery report with per-message status
- Schedules: recurring campaigns with day-of-week and time-of-day
  rules, pause / resume / cancel, run history
- Wallet: balance in UGX and SMS, ledger, invoices
- Plans: purchase (invoice → master marks paid)
- Chat: DM with master, broadcast channel
- Notifications: computed from conditions, dismissible

**Infrastructure**
- Worker sends with rate limits per org (minute and day)
- Failed sends refund automatically
- Opt-out enforced platform-wide, one-click link in every SMS
- Delivery reports via webhook
- Nightly reconcile, daily backup, audit log

**Pool**
- Per-associate opt-in, agreement snapshot, revocable
- Master pool with filters (district, group, source org)
- Pool campaign sends from the system org
- Opt-out propagates to the pool from every entry point

## Not in v1 (parked)

- Automated payment gateway (Flutterwave / Pesapal / MTN MoMo API)
- Registered sender IDs per associate (Phase 5; requires paying client)
- Sub-users per associate (associate_admin can reset passwords but
  cannot create additional users yet)
- Dashboard export as PDF
- Email notifications on campaign complete
- Public API for associates
- Two-factor auth
- Document repository (EgoSMS has one; we do not need it)
- Inline CSV import on the campaign form (associates import first,
  then send)

## Never

- Inbound SMS (account does not support it)
- Two-way conversations
- Multi-currency
- Self-service signup **without** master approval
- Shared contact pool without explicit per-associate permission
- Character counters that ignore the brand prefix

## Change rule

A feature moves from "Not in v1" to "In v1" only with:

1. A named requester (a real associate, not you)
2. A cost estimate in days
3. A written reason in `BACKLOG.md`

Three independent associates must ask before anything moves.