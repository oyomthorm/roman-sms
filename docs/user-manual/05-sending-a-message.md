# 5. Sending a message

This is the core of Roman SMS. You've added contacts (Section 3) and
organized them into groups (Section 4). Now you send a message.

## Before you send: two things to check

Every time you send a message, check these two things first.

**1. Do you have enough credits?** Your wallet balance is on the
dashboard. Sending will fail if the balance is too low for the
campaign you're about to send. If you need more, buy credits (Section
8) first.

**2. Is your brand prefix right?** The brand prefix — the short
identifier at the front of every message — is shown on the message
form. It's what recipients see before your message ("FITTING: Your
fee reminder for Term 2..."). If it's wrong, contact the operator to
change it *before* you send. Change requests take time, and a
campaign sent with the wrong prefix can't be un-sent.

## The three ways to send

Roman SMS supports three modes on the message form. Each is for a
different situation.

- **Standard** — one message, sent to everyone in a group or
  district. This is the everyday mode. Most of your sends will be
  this.
- **Personalized** — a different message to each person, based on a
  spreadsheet you upload. Used when the message needs to be specific
  to each person ("Dear Mary, your daughter Alice's fee balance is
  UGX 45,000..."). Covers fewer recipients than a Standard send but
  gives each one a unique message.
- **Paste numbers** — up to 500 phone numbers you paste directly
  into the form. Used for one-off sends to a small list of people
  who aren't worth adding to the contact list. Skips opt-outs.
  Doesn't add anyone to your contacts.

The form has a small selector at the top — pick the mode first, then
fill in the details below.

`[SCREENSHOT: The New Campaign form with the three-mode selector at top]`

## Sending a Standard message

The simple, everyday case.

1. Open the **Campaigns** page.
2. Click **New campaign**.
3. The mode selector is set to **Standard** by default. Leave it.
4. In **Body**, type the message. This is what recipients will see
   after the brand prefix.
5. Choose **who to send to**:
   - **Group** — pick a group from the dropdown. Every contact in
     that group gets the message (skipping anyone who has opted out).
   - **District** — pick a district to send only to contacts in that
     district. Useful if you have your contacts marked by district
     and want to send to one area.
   - **All contacts** — send to everyone in your organization. Use
     this for organization-wide announcements.
6. Watch the **cost counter** below the message box. It updates as
   you type, showing you the number of credits this message will
   cost per recipient and the total.
7. Click **Send**.

The message goes into the queue. Within minutes (usually seconds),
the dashboard shows it in the sent count and the campaign appears at
the top of your Campaigns list.

### What the cost counter is telling you

When you type, the counter shows something like:

    Length: 143 characters — 1 segment
    Recipients: 187
    Cost: 187 credits

That means: your message is one segment (short enough to fit in one
SMS), you're sending to 187 people, and the total cost is 187
credits.

If you type a longer message, the counter updates:

    Length: 312 characters — 2 segments
    Recipients: 187
    Cost: 374 credits

Two segments per recipient because the message is long enough to
split into two SMS. 187 × 2 = 374 total credits.

**The counter includes the brand prefix.** This is important — the
prefix counts toward the length, so a message that looks like 150
characters is actually 160 with the prefix, which might tip it from
one segment to two. The counter shows the true cost, including the
prefix, so you never get a surprise.

### Send now, or schedule for later?

The form has a **"Send now / Schedule"** toggle. Send now is the
default. If you want to send the message later instead of
immediately, switch to "Schedule". That's covered in Section 6.

## Sending personalized messages

When each recipient needs a different message.

**When to use this.** You have a spreadsheet with each person's name
or balance or some other detail, and you want to include that detail
in each message. Examples:

- "Dear **Mary**, your daughter **Alice**'s fee balance is **UGX
  45,000**, due **20 November**."
- "Hi **John**, your order **#12345** is ready for pickup."
- "Dear **Sarah**, your subscription expires in **5 days**."

Without personalized mode, you'd send one generic message to
everyone. With it, each person gets a message that includes their
specific details.

### Preparing your spreadsheet

Your CSV must have the same columns as a contact import (Section 3)
— at minimum `phone` — plus any extra columns that appear in your
template.

Example CSV:

    name,phone,balance,due_date
    Mary Nakato,0771234567,45000,20 November
    John Ssekandi,0772345678,30000,20 November
    Sarah Achieng,0773456789,0,-

### Writing the message with placeholders

In the message body, use double curly braces to insert a column's
value for each recipient:

    Dear {{name}}, your fee balance is UGX {{balance}}, due {{due_date}}.

For Mary, this becomes:

    FITTING: Dear Mary Nakato, your fee balance is UGX 45000, due 20 November.

For Sarah, this becomes:

    FITTING: Dear Sarah Achieng, your fee balance is UGX 0, due -.

Each recipient gets their own rendering. Any contact whose `name`,
`balance`, or `due_date` is blank in the CSV gets that placeholder
rendered as an empty string — so "Dear , your fee balance is..." can
happen. Check your CSV for missing values before sending.

### The cost of a personalized send

The counter on personalized sends is the sum of per-recipient
segments, **not** "number of recipients × segments in the template".
This is because the placeholder values are different lengths for
different people — Mary Nakato is longer than John Doe, so Mary's
message might be one segment and John's another.

The counter shows the exact total. If a specific row is unusually
long (say, a very long note), that one row might push into a second
segment, adding one extra credit. The counter accounts for this.

### Preview before you send

Click **Preview** to see the first few rows of your spreadsheet
rendered with the template. This is your last chance to catch a typo
in a column name or a mistake in the placeholder syntax before you
commit credits.

`[SCREENSHOT: The personalized preview showing two or three example rows]`

If the preview looks wrong — "Dear {{name}}" showing literally, for
instance — your column name doesn't match. Check the CSV column
headers, then the placeholder names in the body.

### Sending

Once the preview looks right, click **Send**. Same as Standard mode:
the message goes into the queue and will fire shortly.

## Sending to pasted numbers

The fastest mode for small, one-off lists.

**When to use this.** You have up to 500 phone numbers that you want
to message once, and you don't want to add them to your contact list
— a supplier list, a one-time event invite, a test send.

1. Switch the mode selector to **Paste numbers**.
2. Type or paste your phone numbers into the box, **one per line**.
   Spaces and blank lines are ignored.
3. Type your message in the **Body** field.
4. The counter updates as you paste — showing how many valid numbers
   were recognized.
5. Click **Send**.

**What happens to pasted numbers:**

- **Opt-outs are respected.** Any number on the platform-wide opt-out
  list is skipped automatically.
- **Duplicates are skipped.** If you paste `0771234567` twice, it
  goes once.
- **Invalid numbers are skipped.** A number that isn't recognizable
  as a Ugandan phone number is ignored.
- **The numbers are NOT added to your contacts.** They are used for
  this campaign only. If you want to keep them for future sends,
  import them as contacts (Section 3) instead.

**The 500-number limit** is deliberate. If you need to send to more
than 500 numbers, import them as contacts first. Contacts get
opt-out protection, deduplication, and can receive future sends
without re-importing. Pasted numbers are meant for one-off use.

## After you send

Once you click Send, here's what happens.

**Immediately:** You are taken to the campaign detail page. The
message status is "pending" and the queue shows it.

**Within seconds to minutes:** Roman SMS starts sending. The
campaign detail page updates as messages go out. Most campaigns
complete within a minute or two, faster for small sends, slower for
very large ones (rate limits apply — you can't send more than your
plan allows per minute).

**When complete:** The campaign status changes to "complete". You
receive an email confirming the campaign finished, with the
delivery count.

### The campaign detail page

Open any campaign from the Campaigns list to see:

- **Per-recipient status.** Each contact who was in the campaign is
  listed with their delivery status — sent, delivered, or failed.
- **Counts at the top.** How many were sent, delivered, failed.
- **The rendered body.** For personalized sends, the actual text
  each recipient received.
- **Timestamps.** When the campaign was created, when each message
  was sent.

`[SCREENSHOT: A completed campaign detail page with delivery counts and the per-recipient list]`

### What delivered, failed, and pending mean

- **Delivered** — the phone confirmed receipt. This is the goal.
- **Sent** — the message left Roman SMS's system and reached your
  service provider, but the recipient's phone hasn't confirmed
  delivery. Usually becomes "delivered" within seconds. Rarely
  stuck as "sent" — that means the phone was on but couldn't
  receive (out of coverage, network issue).
- **Failed** — the message couldn't be sent. Usually means the phone
  number was invalid or the network rejected it. **Failed messages
  are automatically refunded to your wallet.** You don't pay for
  failures.
- **Pending** — still in the queue. Should go to zero within
  minutes.

## Cancelling a campaign

You can cancel a campaign that's still in progress.

1. Open the campaign's detail page.
2. Click **Cancel**.
3. Confirm.

Messages that have already been sent cannot be un-sent — SMS is
instant. The cancellation stops messages that haven't been sent
yet. If a campaign is entirely queued (e.g. you just clicked send
and the rate limits are still processing it), cancelling stops it
fully.

**Cancellation does not refund you for messages already sent.**
Every message that left the queue — whether it was delivered or not
— has already used a credit. You only save credits by cancelling
before the queue processes them.

For most small campaigns, this means: **cancelling rarely helps
unless you cancel within the first few seconds.** For very large
campaigns (thousands of recipients with minute-rate limits), you can
cancel mid-send and save significant credits.

If you realize you've made a mistake **after** the messages have
gone out, you can't undo it. Send a follow-up correction message if
needed — that's the best you can do.

## What if the campaign doesn't fire

A few reasons a campaign might not send:

**Insufficient credits.** The form usually catches this before you
click Send, but if your balance dropped between page load and
click, the send could fail. Check your wallet balance. Buy credits
(Section 8) and try again.

**Your plan is expired.** Subscriptions have a validity period (for
example, one month). If your current plan has expired, you can't
send until the operator renews it. Check the Billing page (Section
8) for the plan status.

**Your organization is suspended.** If the operator has suspended
your organization (this happens only in serious situations — billing
problems, complaints, abuse), sending is blocked. Contact the
operator.

**Rate limiting.** If you send multiple campaigns in quick
succession, the second and third may wait for the rate limit to
reset. This is normal — it protects the SMS network. Wait a minute
and check again.

## If your message didn't reach someone

**"The campaign says delivered but my recipient didn't get the
message."** A "delivered" status means the phone network accepted
the message and the phone confirmed it. There are a few cases where
"delivered" and "received" diverge:

- The recipient has a dual-SIM phone and only checks one SIM's
  messages.
- The message went to their SMS folder but the phone's app hides
  unknown senders.
- The recipient deleted it without reading.

Nothing you can do from Roman SMS's side — the phone did receive it.

**"The campaign says failed for a specific number."** Failed means
the phone network rejected the message. Common reasons:

- The phone number is invalid (a typo in the contact's record, or a
  number that was cancelled).
- The phone was off and unreachable for too long (network drops
  undeliverable messages after a while).
- The recipient's carrier blocks bulk SMS from certain senders.

Check the number. If it's wrong, fix it and resend. If it's right
and keeps failing, the recipient's carrier may be filtering your
messages — contact the operator to investigate.

## If you see a wrong charge

The cost counter and the actual wallet debit are calculated from
the same underlying rules — they should always match. If you see a
wallet charge that doesn't match what the form showed:

1. Open the campaign detail page. Look at the total segments shown
   there.
2. Open the Billing page. Find the wallet transaction for this
   campaign (search by the campaign's name or date).
3. Compare the two numbers.

If they don't match, contact the operator with both numbers. This
is rare but worth catching quickly.

---

*Section 5 of 10. See `06-scheduling-a-message.md` next.*