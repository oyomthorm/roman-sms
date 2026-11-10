# 6. Scheduling a message

Scheduling lets you write a message now and have it sent later —
once, or repeatedly on a schedule. This is useful for:

- **Recurring reminders.** Fee reminders every Friday. Staff
  meeting notices every Monday morning. A monthly newsletter.
- **Time-sensitive messages.** A message that needs to go out at
  7 AM on a specific day, so parents see it before school starts.
- **Sending when you can't be at a computer.** Write it today,
  have it go out tomorrow while you're busy elsewhere.

## What a scheduled message is

A scheduled message is the same as a regular message — same body,
same recipients, same cost — except that instead of sending it now,
Roman SMS holds it until the scheduled time and then sends it.

You can have multiple scheduled messages. Each is independent.
Each shows up in **Campaigns → Scheduled**.

## Creating a scheduled message

1. Open the **Campaigns** page.
2. Click **New campaign**.
3. Fill in the body and recipients, just like a regular message
   (Section 5 covers all of this).
4. Instead of leaving the mode selector on "Send now", switch it to
   **Schedule**.
5. Set the schedule:
   - **Days of the week** — check the days you want it to send.
     Check multiple days for a repeating schedule. To send once,
     leave all days unchecked and set a single date instead.
   - **Times** — one or more times of day. A message can fire more
     than once per scheduled day (e.g. 8 AM and 5 PM).
   - **Start date** — the earliest date this schedule is active.
   - **End date** — the latest date. Leave blank for "until
     cancelled".
6. Click **Save** (or **Create schedule**).

The schedule appears at the top of **Campaigns → Scheduled**.

`[SCREENSHOT: The Schedule form showing days of the week and a times field]`

## What scheduling does to your wallet

**This is the most important thing to understand about scheduling.**

When you create a schedule, Roman SMS **immediately reserves the
total cost** of every run in your wallet. The credits are debited
at that moment, not when the schedule fires.

### Why this matters

Imagine you schedule a message to 500 people for next Wednesday,
three segments each. Total cost: 1,500 credits. If Roman SMS waited
until Wednesday to charge you, and you spent your balance on
something else between now and then, the Wednesday send would fail
silently — you'd think it went out, but it didn't.

To prevent this, Roman SMS takes the 1,500 credits **now**. Your
wallet shows a debit of 1,500 credits immediately. The message will
go out on schedule because the money is already committed.

### What "reserved" looks like on your wallet

When you look at your wallet after creating a schedule, you'll see
a transaction like:

    -1,500 credits | Schedule reservation | Ref: schedule:42

That means 1,500 credits are held for schedule #42. They're not
spent yet — they'll be spent when the schedule fires. If you cancel
the schedule, you get them back.

### How the reservation is used up over time

If you scheduled multiple runs (say, every Friday for 4 weeks),
your wallet was reserved for all 4 runs at once. On the first
Friday, the actual cost of that run — for the current list of
recipients — is deducted from the reservation. The rest stays
reserved for the remaining runs.

If the schedule runs for 4 weeks at 500 recipients × 3 segments =
1,500 credits per run, that's 6,000 credits reserved up front. On
Friday week 1, 1,500 credits are consumed from the reservation. On
Friday week 2, another 1,500 consumed. Etc.

**Nothing more is charged.** You paid for all the runs when you
created the schedule. The wallet does not debit again on each fire.

### What if the reservation is wrong

Two things can happen between when you create a schedule and when
it fires:

**The list grew.** You scheduled to send to "Form 1 Parents" which
had 500 contacts. Someone adds 10 new parents before Friday. Now
there are 510 contacts. The reservation was for 500 × 3 segments =
1,500 credits. The actual cost would be 510 × 3 = 1,530. Roman
SMS will **pause the schedule** and refund the full reservation. You
get an alert. This is deliberate — Roman SMS won't silently spend
more than you reserved. To fix: cancel the schedule, re-create it
with the current contact count.

**The list shrank.** Ten parents left the school, so the group now
has 490 contacts. The actual cost is 490 × 3 = 1,470. The extra 30
credits are refunded back to your wallet after the run completes.
You don't lose anything.

## Editing a schedule

You can change a schedule after creating it. Changes allowed:

- The **message body**.
- The **recipients** (group or district).
- The **days and times**.
- The **start and end dates**.

### What happens to the reservation when you edit

When you edit a schedule, Roman SMS:

1. **Refunds the old reservation entirely.** The credits return to
   your available balance.
2. **Computes the new reservation** based on the new details.
3. **Debits the new reservation.** The new amount is held.

The net effect on your wallet is the difference. If you had 1,500
credits reserved and your edit changes it to 1,800 credits, you pay
300 more. If your edit changes it to 1,200 credits, you get 300
back.

**If the new reservation costs more than your current available
balance,** the edit fails and the old schedule is unchanged. Roman
SMS refuses to leave you in a state where the reservation isn't
fully funded.

**If you're just fixing a typo in the message body,** the cost is
unchanged and the wallet is unchanged. This is the common case.

## Pausing and resuming a schedule

**Pause** temporarily stops the schedule from firing without
cancelling it. The reservation stays held — no credits are refunded
— but no new runs will fire until you resume.

**Resume** puts the schedule back to active. The next scheduled
time that hasn't passed yet is when the next fire will happen.

Pause and resume don't affect your wallet. They just toggle whether
the schedule is allowed to fire.

Use pause when:

- You're not sure about the message yet.
- Something has changed and you want to think about it before the
  next run.
- You need to temporarily stop sending without losing the
  reservation (which you would if you cancelled and re-created).

## Cancelling a schedule

Cancelling a schedule:

1. **Stops future runs.** The schedule will not fire again.
2. **Refunds the remaining reservation.** Any credits that haven't
   been consumed by past runs are returned to your available
   balance.
3. **Keeps the schedule record.** The schedule shows in your list
   with status "cancelled". You can see what was sent and when.

Cancellation is the normal way to end a schedule. **You almost
always cancel rather than delete.**

## Deleting a schedule

Deleting a schedule is different from cancelling. You can only
delete a schedule that:

- **Has never fired.** `runs_completed = 0`. If the schedule has
  fired at least once, you cannot delete it.
- **Is not currently active.** Pause or cancel it first.

Deletion:

1. Refunds any remaining reservation.
2. **Removes the schedule record entirely.**

**The distinction matters.** A fired schedule is history. If it
sent messages, those messages exist and the campaign record shows
them. Deleting the schedule would lose the record of what was sent
and when. That's why Roman SMS won't let you delete a schedule that
has sent anything.

If you scheduled a message but never let it fire (you cancelled it
before the first run), you can delete it. If it ever fired, cancel
it — you'll keep the record.

## Viewing a schedule

Open any schedule from **Campaigns → Scheduled** to see:

- **The message body.**
- **Who it's going to** (group, district, or all).
- **The schedule** — days of the week, times, start and end dates.
- **The reservation status** — how many credits are held, how many
  have been consumed.
- **The run history** — every time the schedule has fired, what it
  sent, and to how many recipients.

`[SCREENSHOT: A schedule detail page showing the reservation amount and run history]`

## When a schedule doesn't fire

The schedule fires based on the system clock. If a scheduled time
passes and nothing happens, check these:

**The reservation is overcommitted.** If the contact list grew and
the actual cost exceeds the reservation, the run is skipped and the
schedule is paused. Check for an alert notification. Cancel and
re-create the schedule with the new contact count.

**The schedule is paused.** Check its status on the detail page.
If it's paused, click Resume.

**Your plan expired.** If your subscription expired between when
you created the schedule and now, no new fires will happen until
the plan is renewed. Contact the operator to renew.

**Your wallet balance is negative** due to some other action. The
schedule itself is safe (its reservation is protected), but future
manual sends and new schedules will fail. Top up.

## Scheduling vs. sending now: when to use which

- **Send now** for anything time-sensitive right now.
- **Schedule** for:

  - Recurring reminders that happen on a predictable schedule.
  - Announcements you want to go out at a specific future time.
  - Anything you'd otherwise have to remember to log in and do.

**The rule of thumb:** if the message would go out at a specific
time regardless of when you wrote it, schedule it. If it should go
out now, send it now.

## A worked example

Suppose Fitting Secondary School wants to send a fee reminder to
parents every Friday for the rest of the term. Term ends in 8
weeks.

1. **Set up the group.** Assume "Form 1–4 Parents" group exists with
   500 contacts.
2. **Write the message.** "Dear parent, Term 2 fees are due this
   Friday. Pay via *165*3# or contact the bursar. Fitting Secondary
   School."
3. **Check the segment count.** The counter says 2 segments per
   recipient.
4. **Create the schedule.** Every Friday, 8:00 AM, starting this
   Friday, ending on the last Friday of the term.
5. **Total cost:** 500 recipients × 2 segments × 8 weeks = 8,000
   credits reserved.
6. **Confirm.** Your wallet shows -8,000 credits. That money is
   held for the schedule.

Over the next 8 weeks:

- Week 1: Fires. 500 messages sent. 1,000 credits consumed from
  reservation. 7,000 credits still held.
- Week 2: Fires. Another 1,000 consumed. 6,000 still held.
- ...
- Week 8: Fires. 1,000 consumed. 0 held. Schedule completes.

Total cost: 8,000 credits. Each Friday's message was paid for on
the day you created the schedule. You don't think about it again.

If a parent opts out in week 3, the message that Friday goes to
499 instead of 500 — cost 998 instead of 1,000. The 2-credit
difference is refunded after that run.

If Fitting adds 20 new parents in week 4, the message that Friday
would need 1,040 credits instead of 1,000 — exceeding the
reservation by 40. The Friday run is skipped, an alert fires, and
the full remaining reservation is refunded. You (the bursar) fix it
by cancelling and re-creating the schedule with the updated count.

## If a schedule you cancelled keeps showing

Cancelled schedules stay in your list with status "cancelled" so
you can see what was sent. If you want it gone, delete it — but only
if it has never fired. A cancelled schedule that fired can't be
deleted; that's by design (the record of what was sent matters).

## Scheduled messages and email notifications

When a schedule fires, you'll receive the same email notification
a regular campaign sends when it completes. Look for it in your
inbox after the scheduled time.

If you don't receive the email, check:

- **Your email address in your profile.** It's on `/profile`.
- **Your spam folder.** Delivery confirmation emails from
  `no-reply@romansms.com` sometimes end up in spam.
- **Whether the schedule actually fired.** If it didn't, the email
  wouldn't have been sent. Check the schedule's run history.

---

*Section 6 of 10. See `07-your-team.md` next.*