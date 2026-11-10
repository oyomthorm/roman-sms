# 8. Billing — credits, plans, and invoices

**Admin only.** If you are a staff member, you can see your
organization's wallet balance but not the billing details. Skip this
section.

This section explains how credits work, how to get more, and how to
read the records that track every credit in and out of your
organization.

## Two words to know: wallet and plan

**Wallet** — your organization's credit balance. Every message you
send debits from this balance. The dashboard shows it. It never goes
below zero.

**Plan** — a subscription that gives your organization permission
to send messages for a period of time, up to certain rate limits.
Every organization has a current plan. Without an active plan, you
cannot send, even if you have credits in your wallet.

The two work together. A plan says *how fast you can send*. Your
wallet says *how much you can afford to send*. You need both to be
healthy to send messages.

## How credits work

Every message you send costs credits. One credit sends one
**segment** of one SMS. A short message is one segment; a long
message is two or more. See Section 5 for the details on segments.

Credits sit in your wallet. They don't expire on their own — a
credit you buy today can be spent six months from now, as long as
your plan is active. But they can't be sent without a plan.

**What debits credits from your wallet:**

- Every message you send (one debit per segment per recipient).
- Every schedule you create (a reservation, debited immediately —
  see Section 6).
- Any automatic refund of a failed message credits your wallet
  back. But the refund is the *reversal* of a debit; it's not a new
  source of credits.

**What credits your wallet:**

- When the operator grants you credits after you buy a plan.
- When a schedule is cancelled and the remaining reservation is
  refunded.
- When a scheduled run overpays (contacts shrank) and the
  difference is refunded.
- When a message fails at the network level and is refunded.
- A master grant — the operator may occasionally add credits as an
  adjustment (a refund, a bonus, a correction).

Nothing else moves your balance.

## Where your credits come from

**Roman SMS does not sell credits on a self-service basis.** There
is no "Buy credits" button in the app. Instead, the flow is:

1. **You ask the operator** — by chat (Section 9), phone, or
   email. Tell them what you need: how many messages you plan to
   send, roughly. They'll suggest a plan that fits.
2. **The operator issues an invoice** — a document showing what
   you're buying, at what price, with what credits and validity
   period. It appears on your Billing → Invoices page.
3. **You pay** — bank transfer, mobile money, however you've
   agreed with the operator. Pay to the account details on the
   invoice.
4. **The operator marks the invoice paid.** At that moment:
   - Your plan is activated (or renewed).
   - The credits are added to your wallet.
   - You can send.

This usually happens within a few hours of payment. Sometimes
faster, occasionally slower if the operator is away.

**Why isn't it self-service?** Because most customers prefer to
talk through what they need — "I'm sending fee reminders to 500
parents every week for 8 weeks, what plan do I need?" is a
conversation, not a click. And paying in Uganda usually means
mobile money or bank transfer, which don't integrate cleanly with
automatic purchase. When the operator sets up self-service
purchasing, this manual will be updated.

`[SCREENSHOT: The Billing → Invoices page showing a pending and a paid invoice]`

## Reading your plan

Open **Billing** and look at the plan section. You'll see:

- **Plan name** — the plan you're currently on.
- **Credits remaining in the plan** — if your plan has a
  per-period credit limit, this shows how many are left.
- **Valid until** — when the plan's validity period ends. **If
  this date passes, you cannot send until it's renewed** — even
  if you have credits in your wallet.
- **Rate limits** — how many messages per minute and per day the
  plan allows. You won't hit these except on very large sends.

`[SCREENSHOT: The plan section of the Billing page]`

### What happens when the plan expires

**A plan expiring does not delete your credits.** Your wallet
balance stays where it is. But:

- You cannot send new messages or create new schedules.
- Existing schedules fire until they complete or you cancel them.
- You can still log in, see your data, and manage contacts.

When the operator renews your plan (typically as part of a new
invoice), sending resumes immediately.

**If you're about to reach the validity end date** and want to
keep sending, contact the operator a few days before the date.
Renewal usually takes hours from payment, not days.

## Reading your wallet

Open **Billing → Wallet** to see:

- **Current balance** — how many credits you have.
- **Transaction history** — every credit in, every debit out,
  going back to the beginning.

Each transaction row shows:

- **Date** — when the transaction happened.
- **Description** — what the transaction was for. Examples:
  "SMS send", "Schedule reservation", "Plan grant", "Refund",
  "Grant from operator".
- **Amount** — positive for credits in, negative for credits out.
- **Balance after** — your wallet balance immediately after this
  transaction.
- **Reference** — a traceable identifier. `campaign:123` means this
  debit was for campaign #123. `schedule:42` means it was for
  schedule #42.

`[SCREENSHOT: The Wallet transaction list with a few rows visible]`

### Using the reference to trace a debit

The reference is the most useful column. If you see:

    -1,500 credits | SMS send | Ref: campaign:245

You can:

1. Open **Campaigns**, find campaign #245 (it will be near the
   top if it was recent).
2. Confirm the campaign sent to 750 recipients at 2 segments
   each — 750 × 2 = 1,500 credits. Correct.

If the debit doesn't match the campaign, that's when you contact
the operator. Discrepancies are rare but worth catching quickly.

### Reading the balance_after column

The "balance after" column is a snapshot from the moment the
transaction happened. If you add up all your transactions from the
beginning of time, the final balance_after should equal your
current wallet balance. If it doesn't, something is wrong — contact
the operator.

In practice, this reconciliation is guaranteed by how the wallet
is built (it's a strict append-only ledger), so it should always
tie out. It's a checking mechanism you can use if you're worried.

## Reading an invoice

Invoices are at **Billing → Invoices**. You'll see all invoices
for your organization, with status: pending, paid, or cancelled.

Click any invoice to see its details:

- **Invoice number** — a reference.
- **Issued date** — when the operator created it.
- **Amount** — in Ugandan shillings.
- **Status** — pending (not paid), paid, or cancelled.
- **What you're buying** — the plan name, credit count, validity
  period, and rate limits.
- **A PDF download** — save a copy for your records.

`[SCREENSHOT: An invoice detail page showing plan details and amount]`

### The invoice is a snapshot

Once an invoice is issued, it never changes. If the operator
changes a plan's price, or renames the plan, or changes anything
about it, **your existing invoices still show the old details**.

This matters for accounting. The invoice shows what you were
charged and what you were promised, at the moment it was created.
It's a permanent record.

If you download the PDF today, it looks the same as the PDF you
downloaded a year ago. This is by design.

### What "pending" means

A pending invoice has been created by the operator but not yet
paid. It's a request for payment. When you pay, the operator marks
it paid, and the credits flow.

**A pending invoice does not mean you have credits.** If your
wallet shows 0 and you have a pending invoice, you still can't
send. You need to pay the invoice, and the operator needs to mark
it paid.

### What "paid" means

The invoice has been paid. At the moment the operator marked it
paid, your wallet was credited and your plan was renewed. You can
send.

### What "cancelled" means

The invoice was created but will not be paid. Perhaps a mistake,
perhaps a duplicate, perhaps you changed your mind. Cancelled
invoices don't affect your wallet.

## Buying credits: the full flow

If you need more credits — because your balance is low, or you
want to top up before a big send — here's what to do.

**1. Estimate what you need.** Open **Dashboard** and look at
"Days remaining." That number tells you roughly how many days your
balance will last at current spend rate. If it's less than 14 days
and you have sends coming up, you need more credits.

**2. Contact the operator.** Open **Chat**, message the operator,
and say something like: "I need to buy [X] credits for [Y]
months." They'll respond with plan options and prices.

**3. Review the invoice.** The operator issues an invoice. It
appears on **Billing → Invoices**. Check the details — the
amount, the credit count, the validity period. If anything looks
wrong, message the operator before paying.

**4. Pay.** Follow the payment details on the invoice. In Uganda,
this is usually mobile money (MTN, Airtel) or a bank transfer.

**5. Wait for the operator.** Once they confirm your payment, they
mark the invoice paid. This is usually within hours — sometimes
minutes if they're at their computer.

**6. Confirm.** Open **Billing → Wallet**. The credits should
appear as a "Plan grant" row. Your plan's "Valid until" date
should have moved forward.

**7. Send.** You're ready to send messages again.

## When billing doesn't add up

**"I paid but I don't have credits yet."** Wait a bit — the
operator marks invoices paid manually, so there's usually a gap of
minutes to hours between your payment and their mark. If it's been
more than a day, message the operator with your payment reference.

**"I ran out of credits mid-campaign."** If your wallet hits zero
mid-campaign, the campaign may have sent some messages and failed
others. Check the campaign detail page for delivery counts. The
messages that sent are charged; the ones that failed are refunded.
Buy more credits and send a new campaign to catch the rest — there
is no automatic retry.

**"My plan expired but I still have credits."** The credits are
still there. Your plan is what's expired. Contact the operator to
renew your plan, and credits resume working immediately.

**"I don't see the invoice I expected."** Invoices are issued by
the operator. If you agreed to buy credits in a conversation, ask
the operator to issue the invoice — they may have forgotten.
Invoices don't appear automatically.

**"The balance_after on a transaction looks wrong."** Add up the
transaction amounts from the beginning. The last one should match
your current balance. If it doesn't, contact the operator with the
specific transaction date and amount. This is rare — the ledger is
strictly reconciled — but if it happens, it's worth investigating.

**"I want a refund."** Credits are non-refundable once granted.
If you over-bought and don't need them, they'll stay in your
wallet indefinitely — as long as your plan is active, you can use
them. If you have a genuine problem (an invoice was issued for the
wrong amount, a payment was duplicated), message the operator and
they can adjust.

## A small accounting tip

If you're managing your school's or business's budget, do these
three things every month:

**1. Download your invoices.** Save them as PDFs to a folder.
Your accountant will need them.

**2. Export your wallet history.** Print or save the wallet
transaction list. It's the record of every credit spent, with
references to what it was spent on. In a review, this tells you
exactly what your SMS spend was.

**3. Note your current balance and plan expiry.** Write them down
somewhere you'll see them next month. This prevents the "why can't
I send" surprise when a plan expires.

None of this is required by Roman SMS, but it makes the billing
side of your account much easier to manage over time.

---

*Section 8 of 10. See `09-getting-help.md` next.*