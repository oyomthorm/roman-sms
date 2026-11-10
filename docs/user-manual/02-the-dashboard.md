# 2. The dashboard

The dashboard is the first thing you see after logging in. It shows
you, at a glance, how much you've sent and how much you have left.
Nothing on this page changes anything — it's all read-only. To do
something, use the menu on the left.

`[SCREENSHOT: The dashboard with the sidebar on the left]`

## The sidebar

The menu on the left is how you get around. What you see depends on
your role.

**Everyone sees:**

- **Dashboard** — this page.
- **Contacts** — your contact list and imports.
- **Groups** — your groups of contacts.
- **Campaigns** — messages you've sent and messages you've scheduled.
- **Templates** — saved message bodies you can reuse.
- **Billing** — your wallet and invoices.
- **Chat** — a direct line to the operator.
- **Reports** — delivery summaries and usage.
- **Profile** — your own account.

**Administrators also see:**

- **School users** — add, remove, and manage your staff.
- **Settings** — your organization's name and preferences, plus
  whether to share contacts with the operator's master contact pool.

**Staff members with a department** (e.g. a bursar, a DOS) see a
smaller list. They don't see "School users" or "Settings", and
"Contacts", "Groups", "Campaigns", and "Templates" show only their
own department's items plus shared items.

## The top of the page

Above the sidebar, across the top, you'll see:

- **Your organization's name** — on the left, or next to a small
  logo.
- **The notification bell** — the count of new notifications (see
  below).
- **Your email address** — a dropdown with **Profile** and **Log
  out**.

## The dashboard itself

The dashboard is a grid of boxes. Which boxes you see depends on
whether you have any activity yet.

### Wallet balance

The most important number on the page. This is how many credits you
have available to send messages.

- **Big number:** your current balance.
- **Days remaining:** an estimate based on how fast you've been
  spending. If you usually send 200 credits a week, this tells you
  how many weeks your balance will last.

If this number is low and you need to send, buy credits before you
try. See Section 8.

`[SCREENSHOT: The wallet balance box]`

### Messages sent (last 30 days)

How many messages you've sent in the last 30 days. This is the count
that consumes credits.

Below it, three related numbers:

- **Delivered** — messages confirmed to have reached the recipient's
  phone.
- **Failed** — messages that were never sent (network issue, provider
  error). These are refunded to your wallet automatically.
- **Pending** — messages still in the queue. Should go to zero
  within minutes of sending.

### 30-day trend

A simple chart showing messages sent per day over the last 30 days.
Each bar is one day. Empty days show as empty bars, so the chart
always shows the full month.

Use this to spot patterns: are you sending every Friday? Did you skip
a week? Useful for planning.

`[SCREENSHOT: The 30-day trend chart]`

### Recent activity

A short list of what has happened recently in your organization:
messages sent, campaigns scheduled, schedules cancelled, imports
completed.

### Notifications

At the top of the page, a bell with a number. Click it to see what
needs your attention. Common notifications:

- **Wallet is running low** — you have enough for the next few
  messages but not many. Buy credits soon.
- **Plan is expiring** — your current plan's validity period is
  almost over.
- **No contacts yet** — you haven't added any contacts. Start with
  Section 3.
- **An import has errors** — a CSV you imported had rows that
  couldn't be added.

Click any notification to go to the page where you can fix it. Click
the **×** on a notification to dismiss it — you won't see it again
unless the same condition comes back later.

`[SCREENSHOT: The notifications panel with one or two notifications shown]`

There is no "inbox" for notifications. They are recalculated every
time you visit the page. If a problem goes away — say, you buy
credits and the wallet is no longer low — the notification
disappears on its own.

## What the dashboard does not show

The dashboard does not show:

- **Individual message contents** — that's on each campaign's detail
  page.
- **Individual contact details** — that's on the Contacts page.
- **Who sent what** — that requires opening each campaign's detail
  page, or using the Reports page.
- **Other organizations' data** — you only see your own. Even the
  operator's numbers are not visible to you here.

## If the dashboard looks wrong

A few common concerns and what to do:

**"My wallet balance is zero but I know I bought credits."**
Wait a minute and refresh. If it's still zero, check the Billing
page (Section 8) — the transaction history will show whether the
credits arrived. If they haven't, contact the operator.

**"I've sent messages but the count is zero."** The 30-day count
includes only messages that were successfully sent. Messages that
failed at the dispatch stage and were refunded don't count. If you
expect to see a send from today and it's not there yet, the messages
may still be pending — check again in a few minutes.

**"The days remaining number is way off."** It's an estimate based
on recent spend. If you've just sent a large campaign, it will show
a much shorter runway than usual, because it's assuming you'll keep
sending at that rate. It recalculates as the days pass.

---

*Section 2 of 10. See `03-contacts.md` next.*