# 10. Troubleshooting

When something isn't working, look for the problem in the list below.
The problems are alphabetical. Each entry tells you the most likely
cause, what to do, and when to stop and ask the operator.

If your problem isn't here, go back to Section 9 — chat is the
fastest way to reach the operator.

## Account suspended or terminated

**Symptom:** You try to log in and see a message saying your
account is suspended or terminated.

**Most likely cause:** An administrator (or the operator) has
deliberately changed your account status. This does not happen
accidentally.

**What to do:**

- If you are a staff member: contact your school or business
  administrator. They can reactivate you.
- If you are the administrator: contact the operator. Account
  suspension for an admin usually indicates a payment or
  compliance issue that needs to be resolved.

**When to stop and ask:** Immediately. If you're the admin and
you're suspended, you cannot fix it yourself. Chat or email the
operator.

## "Insufficient credits" when you have credits

**Symptom:** You try to send a campaign or create a schedule, and
the form says "Insufficient credits" even though your wallet shows
a positive balance.

**Most likely cause:** One of:

- Your plan has expired, and the credits aren't available because
  they can't be sent without an active plan.
- The cost of the campaign is more than your available balance —
  check the counter on the form against your dashboard balance.
- A recent schedule reservation is holding credits that haven't
  been released yet.

**What to do:**

1. Check your plan status on **Billing** — is the "Valid until"
   date in the future?
2. Look at the cost counter on the campaign form. Is the total
   greater than your dashboard balance?
3. Check **Campaigns → Scheduled** for schedules with active
   reservations. Each holds credits.

**When to stop and ask:** If your plan is active, your balance is
higher than the campaign cost, and you have no active schedules,
but it still says insufficient. Something is wrong with the
wallet — the operator needs to investigate.

## Campaign shows failed for one number

**Symptom:** A campaign was sent. Most recipients show "delivered"
or "sent". One or two specific numbers show "failed".

**Most likely cause:** The number was invalid (typo in the
contact's record), the phone was off for too long to receive, or
the phone carrier rejected the message.

**What to do:**

1. Open the contact's record and check the phone number. Compare
   it to what you know about the person. A typo — 0771234567 vs
   0771234576 — is the most common cause.
2. If the number is wrong, edit it. Then send a new campaign to
   that group or contact to catch the failed recipient.
3. If the number is correct and keeps failing, the recipient's
   carrier may be blocking bulk SMS from the platform's sender
   ID. This is rare but happens.

**When to stop and ask:** If the number is correct and continues
to fail across multiple campaigns, ask the operator to investigate.
It may be a carrier-level block on that specific number.

## Campaign stuck on "pending"

**Symptom:** You click Send. The campaign is created. The status
shows "pending". It's been more than 5 minutes and nothing has
changed.

**Most likely cause:** The worker (the background process that
sends messages) is either very backed up, or there's an issue with
the SMS provider. Rate limits also delay large campaigns —
they're processed gradually to stay within the plan's per-minute
budget.

**What to do:**

1. Wait 5 more minutes. Small campaigns complete quickly. Large
   campaigns (thousands of recipients) take minutes at the plan's
   rate limit.
2. Check the campaign detail page. Is there a per-recipient status
   showing "sent" for at least some recipients? If yes, the
   campaign is working — just slowly.
3. Reload the page. Sometimes the display lags behind the actual
   status.

**When to stop and ask:** If a small campaign (under 100
recipients) has been pending for more than 15 minutes, and the
detail page shows zero sent messages, contact the operator. The
worker may be stuck.

## Can't create a contact — no group in dropdown

**Symptom:** You open the "Add contact" form. The Group dropdown
is empty or only shows options you don't want.

**Most likely cause:** Your organization has no groups in your
department, or the groups available aren't yours.

**What to do:**

1. If you haven't created any groups yet: go to **Groups** and
   create one first (Section 4).
2. If you're a staff member with a department: you only see groups
   from your own department plus shared groups. If you need a
   shared group, ask your administrator to create one.

**When to stop and ask:** If you're sure there are shared groups
your administrator has created, but you don't see them, ask your
administrator to check.

## Can't log in

**Symptom:** You enter your email and password, click Log in, and
nothing happens, or you see an error message.

**Most likely cause:** One of:

- Wrong email or password.
- Your account is suspended or terminated.
- Browser cookie issue.

**What to do:**

1. Check the email address carefully. Spelling matters. Is there a
   typo?
2. If you're not sure of your password, use **Forgot password?**
   on the login page to reset it.
3. If it says "invalid email or password" (not "suspended" or
   "terminated"), the credentials are wrong. Reset your password.
4. If the page doesn't respond at all, try a different browser or
   clear your browser cookies for `romansms.com`.

**When to stop and ask:** If you've reset your password and still
can't log in, or if you see "account is inactive" and you don't
know why, contact the operator.

## Changes didn't save

**Symptom:** You edited a contact, group, or template. You clicked
Save. Later, you open the same record and the old values are back.

**Most likely cause:** The save didn't go through — an error
message may have appeared briefly and disappeared, or your
internet connection dropped. Rarely, a browser bug.

**What to do:**

1. Try again. This time, watch for any error message after clicking
   Save.
2. If the edit involves a phone number or email that's already in
   use, the save will fail with an error. Check the message.
3. Reload the page before editing, in case you're seeing stale
   content.
4. Check your internet connection. A drop mid-save loses the
   change.

**When to stop and ask:** If you consistently cannot save a
specific record, ask the operator. There may be a data issue with
that record.

## Chat doesn't load

**Symptom:** You open the **Chat** page and it's blank, shows a
loading spinner forever, or shows an error.

**Most likely cause:** Network issue, or a temporary server
problem.

**What to do:**

1. Reload the page. Chat uses polling, and a reload often fixes
   temporary stuck states.
2. Check your internet connection.
3. Try a different browser.

**When to stop and ask:** If chat consistently doesn't load, use
the contact details on your latest invoice (email or phone) to
reach the operator. Section 9 covers this in more detail.

## Contact isn't showing up in the group

**Symptom:** You added a contact to a specific group. Later you
open that group and the contact isn't there.

**Most likely cause:** One of:

- You're looking at a different group than the one they were added
  to.
- The contact was moved to a different group.
- There was a save error you didn't notice.

**What to do:**

1. Go to **Contacts** and search for the contact by name or phone.
   Are they there? If yes, open the record to see which group
   they're actually in.
2. If they're in a different group, edit and change the group.
3. If you can't find them at all, they may not have been saved —
   re-add them.

**When to stop and ask:** If you've verified the contact exists
and belongs to the group but doesn't show in the group's list,
ask the operator. There may be a display cache issue.

## Dashboard shows wrong numbers

**Symptom:** You know you sent X messages yesterday, but the
dashboard shows a different number.

**Most likely cause:** The dashboard's 30-day count includes only
successfully-sent messages, and the "sent" count specifically
includes messages that left Roman SMS whether or not they were
confirmed delivered. A campaign that failed at the network level
may not appear in the count.

**What to do:**

1. Reload the page. The dashboard recalculates on every load.
2. Look at the specific campaign detail page to check what it
   actually sent.
3. For a specific period's numbers, use **Reports** rather than
   the dashboard — reports are more granular.

**When to stop and ask:** If the numbers are dramatically off
(hundreds of messages), ask the operator. A few-message
discrepancy is usually the display logic; hundreds is a real
problem.

## Forgot password

**Symptom:** You can't remember your password.

**Most likely cause:** Normal — this happens.

**What to do:**

1. On the login page, click **Forgot password?**
2. Enter the email address you use to log in to Roman SMS.
3. Check your email for a password-reset link. Click it. Set a new
   password.
4. The reset link expires in 24 hours. If it's expired, request a
   new one.

**When to stop and ask:** If you don't receive the reset email
within a few minutes and you've checked your spam folder,
contact the operator.

## Import failed — most rows skipped

**Symptom:** You imported a CSV of contacts. The report shows most
rows skipped, with various reasons.

**Most likely cause:** One of:

- Phone numbers in the CSV are not in a recognized Ugandan format.
- There are no headers in the first row of the CSV, so the system
  can't find the `phone` column.
- Most of the numbers are already in your contact list.
- Your file uses a format the system can't read (`.xlsx` instead
  of `.csv`).

**What to do:**

1. Open the import report. Look at the reasons per row.
2. If the reason is "invalid phone", check that the CSV's phone
   column has numbers like `0771234567` (not `+256` at the
   start of one row and `077` at the start of another — be
   consistent).
3. If the reason is "duplicate", the contacts are already in your
   list. This is fine — you don't need to re-import them.
4. If you're not sure what's wrong, download the error CSV and
   look at the specific rows that failed.

**When to stop and ask:** If a small file (under 50 rows) with
obviously-correct phone numbers is failing across the board,
ask the operator. There may be an issue with the file encoding or
format that isn't obvious from the error report.

## Message says delivered but wasn't received

**Symptom:** The campaign detail page shows "delivered" for a
specific recipient. They say they never got the message.

**Most likely cause:** "Delivered" means the phone network
accepted the message and the phone confirmed receipt. If the
person says they didn't get it, the possibilities are:

- They got it but don't remember (spam folder, or the SMS was
  buried among other messages).
- They have a dual-SIM phone and checked the wrong SIM.
- Their phone's SMS app is hiding unknown senders.
- The message was delivered to a number that looks like theirs
  but isn't (typo in their contact record).

**What to do:**

1. Check the contact's phone number in your records against what
   they tell you their number is. A one-digit difference is
   common.
2. Ask them to check their phone's SMS app again — many phones
   sort unknown senders separately.
3. If their number is wrong in your records, fix it and re-send.

**When to stop and ask:** If the number is correct, they've checked
their phone thoroughly, and this happens repeatedly for the same
person, ask the operator. There may be a carrier-level delivery
issue with their number.

## Notifications won't go away

**Symptom:** You dismiss a notification but it keeps coming back.

**Most likely cause:** Notifications are recomputed on every page
load from live conditions. If the condition still applies, the
notification keeps appearing. Dismissing a notification hides it
once, but doesn't fix the underlying problem.

**What to do:**

1. Look at what the notification is about. Wallet low? Plan
   expiring? Import with errors?
2. **Fix the condition.** Buy credits, renew the plan, review the
   import. Once the condition no longer applies, the notification
   disappears.
3. There is no way to permanently dismiss a notification without
   fixing the condition. This is deliberate — the notification is
   there to remind you of something that needs attention.

**When to stop and ask:** If a notification describes a problem
you cannot fix (say, "your organization is suspended" when you're
not suspended), contact the operator. The notification may be
based on incorrect data.

## Opt-out couldn't be reversed

**Symptom:** A contact asked to receive messages again. You can't
un-opt-out them.

**Most likely cause:** Opt-outs are permanent by design, at the
platform level. No user role can reverse an opt-out. Not you, not
your administrator, not even the operator (except in very rare
circumstances).

**What to do:**

- The phone number stays opted out.
- If the contact needs to receive messages urgently (medical
  alerts, critical notices), the workaround is a different phone
  number, or a direct phone call.
- Do not try to add the same number with different spacing or
  formatting — the system normalizes phone numbers and will still
  respect the opt-out.

**When to stop and ask:** If a contact insists they never opted
out, ask the operator to investigate. This is unusual — opt-outs
are triggered by specific actions — but possible if someone else
used their phone number.

## Schedule didn't fire

**Symptom:** You scheduled a campaign. The scheduled time has
passed. No messages were sent.

**Most likely cause:** One of:

- The schedule is paused.
- The plan expired.
- The contact list grew beyond the reservation (overage guard
  paused the schedule).
- Wallet balance is negative.

**What to do:**

1. Open the schedule detail page. What's the status? Active?
   Paused? Completed?
2. If paused — check why. If the reason mentions "overage," the
   contact count grew. Cancel and re-create with the current
   count.
3. Check your plan on **Billing** — is it active?
4. Check your wallet balance on the dashboard.

**When to stop and ask:** If the schedule shows "active," the
plan is active, the wallet is positive, and the scheduled time
passed without a fire, contact the operator. The scheduler may be
stuck.

## Schedule fired twice

**Symptom:** A scheduled message sent to your recipients twice in
close succession.

**Most likely cause:** Two separate schedules exist that happen to
fire at similar times. Or, a scheduled fire and a manual send were
triggered near each other.

**What to do:**

1. Open **Campaigns → Scheduled** and look for duplicate
   schedules with the same or similar settings.
2. Check **Campaigns** for duplicate campaigns from the same
   period.
3. If you find two schedules that duplicate each other, cancel
   one.

**When to stop and ask:** If you can only find one schedule and it
fired twice, ask the operator. There may be a duplicate event in
the worker's log that indicates a real bug.

## Wallet balance is 0 but I know I have credits

**Symptom:** Dashboard shows 0 credits. You know you bought
credits recently.

**Most likely cause:** One of:

- The credits were consumed by recent sends.
- A schedule reservation is holding them.
- The invoice you paid hasn't been marked paid yet by the
  operator.

**What to do:**

1. Open **Billing → Wallet**. Look at the recent transactions.
   Are there debits you didn't expect?
2. Check **Campaigns → Scheduled**. Any schedules with active
   reservations? Each holds credits.
3. Check **Billing → Invoices**. Is there a pending invoice? If
   yes, the operator may not have marked it paid yet.

**When to stop and ask:** If you've checked all three and
everything looks correct, but your balance is still 0, contact the
operator. There may be a billing discrepancy they need to
investigate.

---

*Section 10 of 10. End of manual.*