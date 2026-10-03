# Onboarding an associate

Roughly 15 minutes from first contact to first campaign. Do it as a
shared session — you driving, them watching — for the first three
associates. After that a written guide is fine.

## Two paths in

1. **Master creates directly.** Master console → Associates → New
   associate. Full control over slug, brand prefix, district, and
   initial password. Use this when you have already spoken to them.
2. **Self-signup.** They submit at `/signup`. You approve at
   `/master/signups`. Starter credits are granted automatically on
   approval. Use this for inbound leads you have not talked to yet.

## Before the call

- [ ] They have paid, or agreed to pay, on a specific tier.
- [ ] You know their brand name (what recipients will see as prefix).
- [ ] You know their district (area of operation).
- [ ] You know the email they will use for their admin login.

## The call (15 minutes)

1. **Create or confirm the org.** For a master-created org: fill name,
   slug (lowercase, dashes), brand prefix (≤ 20 chars), district,
   admin email, initial password. For a self-signup org: open the
   request at `/master/signups/<id>` and click Approve.

2. **Grant a plan.** On the org detail page, assign the tier. SMS and
   the UGX value appear in their wallet. Confirm the balance.

3. **Hand off credentials.** For a master-created org, they use the
   password you set. For a self-signup, they receive a welcome email
   with a password-setup link. Ask them to change the password
   immediately (Profile → Change).

4. **Walk through contacts.** Show them:
   - Contacts → Add for a single entry
   - Contacts → Import CSV for a batch. Download the sample first — it
     shows the exact format including districts. Point out that after
     the import they land on a report page showing every skipped row,
     downloadable as a CSV they can fix and re-upload.
   - Groups to organise contacts

5. **Send a test campaign.** Campaigns → New. Pick a small group. Send
   to themselves or a team member. **Point out the character counter
   below the message body** — it shows characters, segment count, and
   the shilling cost, and it counts the brand prefix, so the number is
   the real delivered length. If the counter crosses a segment
   boundary, the cost doubles. Tell them this so they are not
   surprised by the wallet debit.

   Mention the "Paste numbers" option: for one-off sends to a small
   list that is not worth adding to their contacts, they can paste up
   to 500 numbers and skip the contact import step. Duplicates and
   opt-outs are handled automatically.

6. **Explain scheduling.** Still on the new-campaign form, show the
   "Send now" / "Schedule" toggle. If they send a recurring message
   (fee reminders, weekly promotions), the schedule option lets them
   define days of the week and times of day, plus a start and end
   date. They can pause, resume, or cancel a schedule from
   Campaigns → Schedules. Credits are debited per run, not reserved
   up front.

7. **Explain the wallet.** Wallet shows balance in UGX and SMS, plus
   invoices and every transaction. When they need more, they choose a
   tier on the Plans page, which generates an invoice. They pay by
   mobile money or bank; you mark it paid; SMS appears.

8. **Show chat.** The Chat link opens a DM with Roman SMS support and
   a broadcast channel where all associates can talk.

9. **Mention the opt-out link.** Every message carries a one-click
   unsubscribe link. Recipients who use it are removed from every list
   on the platform — this is a feature, not a bug. Tell them so they
   are not surprised when a customer disappears from their list.

10. **Record the permission decision.** If they want to contribute to
    the master pool, walk them through Settings → Enable contact
    sharing. If not, do not push.

## After the call

- [ ] Send a confirmation email with login URL, their slug, and your
      contact details.
- [ ] Note in the audit log (any action you took is already there).
- [ ] Set a reminder to call them in 30 days.

## What to watch in the first month

- **Zero campaigns.** They signed up, they are stuck. Call them.
- **High failure rate.** Check the failed logs; usually bad phone
  numbers. Point them at the import report.
- **Low balance warning.** The notification fires under 100 SMS.
- **Segment cost complaints.** Associates who assume 160 characters of
  body are surprised when the prefix pushes them over. The counter on
  the form prevents this, but new users miss it. Point them at it.
- **No chat messages.** Fine. Most associates are quiet until they need
  something.

## Red flags

- **They ask to buy 100,000+ credits on the first day.** Either a very
  good client or an abusive sender. Watch their first campaign.
- **They import a purchased list.** Refuse. The associate agreement
  requires consent. Ask them to confirm the source in writing.
- **They ask for a sender ID.** Explain the constraint (ADR-002). Only
  offer the registered sender ID path if they are prepared to pay the
  setup fee upfront (Phase 5).