# Part 5 — School / business admin user guide

This guide is for the **school administrator** — the `associate_admin`
user (with `department=None`) of a school or business org. If you are
the platform operator, read Part 4 instead.

The role name is `associate_admin`, but the person is called "school
admin" in the product for schools and "business admin" for businesses.
The permissions are identical; only the onboarding copy differs once
#51 ships.

## 5.1 What the school admin sees

When you log in, the sidebar shows:

- **Dashboard** — usage charts, wallet balance, recent activity
- **Contacts** — your contact list, groups, imports
- **Campaigns** — send history, schedules, new campaign button
- **Templates** — message templates
- **Billing** — wallet, invoices, plan status
- **Chat** — messages from master + broadcast
- **Reports** — usage and delivery summaries
- **School users** — user management (this page only exists for
  associate_admin with `department=None`; see §5.7)
- **Settings** — org settings, pool sharing
- **Profile** — your own account

If you log in with a department set (rare for an admin, more common for
a bursar or dean), "School users" and "Settings" are hidden and your
Contacts/Campaigns views are filtered to your department plus shared
records.

## 5.2 First login — setting your password

When master approves your signup, you receive a welcome email with a
password-set link. The link expires in **24 hours**.

1. Open the email, click the link.
2. Enter a new password (twice). Requirements: [VERIFY: minimum length
   and complexity rules — check `services/users.py` or the
   `set_password` form validation].
3. Submit. You are redirected to `/auth/login`.
4. Log in with your email and the new password.

If the link expires, contact the operator. They can trigger a reset
email from the master console.

## 5.3 The dashboard

**Route:** `GET /dashboard`

Your home page. Shows, per `02-architecture.md` §2.15:

- **Sent (30d)** — messages with status `sent`, `delivered`, or
  `delivery_failed`. This is the count that consumes credits.
- **Delivered (30d)** and **Delivery failed (30d)** — subsets
  confirmed by the delivery webhook.
- **Failed (30d)** and **Pending (30d)** — independent counters for
  messages that were never sent (failed at dispatch) and are still
  queued.
- **30-day trend** — inline SVG chart, one slot per day including
  zero-days.
- **Wallet balance** and **days remaining** at current spend rate —
  computed from `sms_send` debits.
- **Notifications** — computed live from your org's state (low balance,
  plan expiring, no contacts, etc.). No stored inbox: a notification
  disappears when the underlying condition clears.

If a notification bothers you, dismiss it. `NotificationDismissal`
records the dismissal for your user; the notification returns only if
the condition resolves and recurs.

## 5.4 Contacts — list, create, import

**List:** `GET /contacts`

Every contact in your org (or, if you have a department, your
department + shared). Filter by group, by district, by opt-out status.
Search by name or phone.

**Create one:** `GET`/`POST /contacts/new`

Fields: name (optional), phone (required, Ugandan format), group
(optional), district (optional), notes. The phone is normalized via
`phones.normalize_ug` — `0771...`, `+256771...`, and `256771...` all
become the same canonical form. Duplicate phones within the org are
rejected.

**Import:** `GET`/`POST /contacts/import`

CSV upload. The file must contain a `phone` column; `name`, `group`,
`district`, `opted_out` are optional. Every row is normalized,
checked against `OptOut`, checked for in-file duplicates and existing
database duplicates, and imported or skipped with a reason.

After import, you're redirected to `/contacts/imports/<id>` — a
persistent report showing:

- Counts: imported, skipped (invalid phone), skipped (opted out),
  skipped (duplicate in file), skipped (duplicate in DB)
- Filter tabs to see each category
- A downloadable error CSV containing every skipped row and its reason

The report is not transient — you can return to it later. It stays
available indefinitely.

**Opt-out:** `POST /contacts/<id>/optout`

Marks a contact as opted out. Every opt-out path (this button, the
public opt-out landing page, an import with `opted_out=1`) calls
`propagate_opt_out(phone)`, which touches both the `OptOut` table and
any pool contacts for that phone. Opt-outs are respected everywhere —
no campaign will send to an opted-out phone, even if the contact row
itself says otherwise.

## 5.5 Groups

**List:** `GET /groups`

Groups organize contacts for targeted campaigns. Each group has a name,
a department scope (from your department at creation time), and a
contact count. The list shows only your department's groups plus
shared groups.

**Create:** `GET`/`POST /groups/new`

Fields: name, description. The department is set to your
`current_user.department` automatically — you cannot choose it. If
you have `department=None` (school admin), all groups you create are
shared, visible to every user in the school.

**Detail:** `GET /groups/<id>`

Shows the group's contacts, with the option to add contacts directly
by phone or import from a CSV. Contact count is `null` on the detail
endpoint until rendered — this is by design; the count is computed on
the page.

**Edit / delete:** `GET`/`POST /groups/<id>/edit`, `POST /groups/<id>/delete`

Delete is a hard delete — the group row is removed, its contacts are
unlinked (contacts are not deleted, only the group_id reference is
cleared). **No undo.** Do not delete a group you might need.

If a group is referenced by a schedule, delete will still proceed —
the schedule's `group_id` becomes orphaned (see backlog #38 — the
service does not currently guard against this). Cancel the schedule
first if it matters.

## 5.6 Campaigns — send now

**New campaign:** `GET`/`POST /campaigns/new`

Three modes:

1. **Standard** — one body, sent to a group or district or all contacts.
2. **Personalized (CSV)** — a CSV of recipients with per-row columns;
   the body uses `{{column}}` placeholders rendered per row. See
   `03-features.md` §3.1 for the design.
3. **Paste numbers** — up to 500 pasted phone numbers as an ad-hoc
   recipient list. Opt-outs and duplicates are skipped.

The campaign form shows a live character/segment counter as you type.
The counter is client-side JS that mirrors the server's segment
arithmetic, including the brand prefix. The final cost is the sum of
per-recipient segments — not `recipients × body_segments` — because
per-recipient bodies can differ in length under the personalized
mode.

**Submit.** `campaigns.create_campaign` runs the full send flow:

1. Resolve recipients (contacts minus opt-outs, filtered by
   group/district/all)
2. Render each recipient's body
3. Compute total segments
4. `check_can_send` — org active, subscription active, wallet balance
   sufficient
5. Create `Campaign` row, `db.session.flush()` for the ID
6. `wallet_svc.debit(org.id, total_segments, reason='sms_send',
   reference=f'campaign:{id}')`
7. Create `MessageLog` rows (one per recipient, status `pending`)
8. Create `SendQueue` entry with `run_after=now`
9. `db.session.commit()`

**Critical:** steps 5–9 are a single transaction. If the debit fails,
no Campaign row exists. If the Campaign is created and a later step
fails, rollback reverses both. The wallet and the campaign are always
consistent.

**Detail:** `GET /campaigns/<id>`

Shows per-message status, delivered count, failed count, and the
rendered body for each recipient (in the `MessageLog.body` column).
You can see exactly what was sent to whom.

**Cancel:** `POST /campaigns/<id>/cancel`

Cancels a campaign that is still in flight. Messages not yet sent are
marked cancelled. Refund behavior for partially-sent campaigns is
**not specified today** (backlog #16) — currently the campaign
cancellation does not refund un-sent segments. Do not rely on cancel
as a refund mechanism. If a campaign is wrong, the wallet cost is
already incurred.

## 5.7 Campaigns — schedule for later

**New schedule:** from `/campaigns/new`, mode "Schedule"

Fields: body, group/district filters, days of the week, time(s) of day,
start and end dates. Times are in your org's timezone
(`SCHEDULER_TZ_OFFSET_HOURS`, default UTC+3 for Uganda).

**Pre-reservation.** Creating a schedule debits the wallet **at create
time** for the full commitment: `segments_per_run × len(times)`. This
is the #44 behavior. The `CampaignSchedule.credits_reserved` column
records the amount held.

If you schedule 3 runs of 500 recipients at 3 segments per message,
`credits_reserved = 500 × 3 × 3 = 4500`. Your available balance drops
by 4500 immediately. When each run fires, the actual segment count is
deducted from the reservation — no additional wallet debit.

**At fire time.** `materialize_run` in the worker:

- If `credits_reserved IS NULL` (a legacy schedule from before #44),
  old behavior: debit at fire.
- If `credits_reserved` is set: skip `check_can_send`, skip
  `wallet_svc.debit`, decrement `credits_reserved` by actual segments.
  - If `actual > credits_reserved` (contacts grew), skip the run,
    refund the full reservation with reason `schedule_overage_refund`,
    and pause the schedule with a clear reason. This is a guard
    against silently spending more than you committed.
  - If `actual < credits_reserved` (contacts shrank), fire normally
    and refund the difference at completion with reason
    `schedule_complete_refund`.

**Cancel:** refunds the remaining reservation with reason
`schedule_cancel_refund`, sets `credits_reserved=0`, marks the
schedule cancelled. The wallet is credited immediately.

**Edit:** `GET`/`POST /campaigns/schedules/<id>/edit` (from #16)

Change times, body, name, or recipient filters after creation. The
reservation adjusts:

- Old `credits_reserved` is refunded (`schedule_cancel_refund`)
- New commitment is computed and debited (`schedule_reserve`)
- If the new reserve raises `InsufficientCredits`, the refund is
  reversed — wallet is net-zero on failure
- Net wallet change = new reserve − old reserve, so a same-size edit
  costs nothing

**Delete:** `POST /campaigns/schedules/<id>/delete`

Only allowed if `runs_completed == 0` (never fired) and the schedule
is not active. Refunds remaining reservation, hard-deletes the row.
Fired schedules must be preserved for audit — you cannot delete them.

**Pause / resume:** `POST /campaigns/schedules/<id>/pause`,
`/resume`. Pause holds the reservation; resume continues. Neither
touches the wallet.

## 5.8 School users — managing your school's team

**Route:** `GET /school/users`

**This page only exists for `associate_admin` with `department=None`.**
If you are a dept-scoped admin or an `associate_user`, the page returns
404 or is hidden from the sidebar.

The user list shows every user in your org, with columns: email, name,
role, department, status, created date, last login. Clicking the email
opens the user detail page (§5.8.3).

### 5.8.1 Creating a user

`GET`/`POST /school/users/new`

Fields: email, name, password (initial, or leave blank for a set-link
email — [VERIFY: exact behavior on the create form]), role
(`associate_admin` or `user`), department (dropdown: None, bursar, DOS,
dean, HT).

**Critical rule:** `associate_admin` requires `department=None`. If
you select `associate_admin` and pick a department, creation is
rejected — a dept-scoped user must be `role='user'`. This is a
security invariant from the design (see `PERMISSIONS.md`).

A school can have multiple associate_admins (with `department=None`).
No upper limit. The first admin is created during signup approval
(Part 4, §4.4); subsequent admins are created here.

### 5.8.2 Editing a user

`GET`/`POST /school/users/<id>/edit`

Fields: name, email, department. Changing a department moves the user's
data visibility from one scope to another — the user's existing
records keep their old department, but their future records will carry
the new one.

You **cannot** change a user's role via this form. Roles are set at
creation and are effectively permanent. If you need to change a role,
delete and recreate the user (which loses audit attribution — see
§5.8.4).

### 5.8.3 User detail page

`GET /school/users/<id>`

Read-only activity summary. Shows:

- Identity card: email, name, status badge, role, department, created
  date, last login
- Four stat cards: campaigns (all-time), campaigns (30d), active
  schedules, audit events
- Recent campaigns table (last 10, links to detail)
- Recent schedules table (last 10, links to detail)
- Recent audit activity (last 20 events where `actor_id = user.id`)

This is the page to visit when you want to know "how many campaigns
has the bursar sent this term."

### 5.8.4 Status — suspend, terminate, reactivate, delete

Three states, four actions. Read `02-architecture.md` §2.4 for the
full state table; the operational summary:

**Suspend:** `POST /school/users/<id>/suspend`

Blocks new sends at `/campaigns/new` (flash error). Login still works.
Read-only access. Existing scheduled fires continue — the school
committed to those sends when the schedule was created, and the
reservation was already debited.

Use when: a user is on leave, or under investigation, but you might
reinstate them.

**Terminate:** `POST /school/users/<id>/terminate`

Blocks login entirely (`is_active_flag=False`). All access ends.
Existing scheduled fires still fire — same reasoning as suspend.

Use when: a user has left the school permanently and you want to fully
revoke access but preserve their audit trail.

**Reactivate:** `POST /school/users/<id>/reactivate`

Restores `status='active'` and `is_active_flag=True`. The user can log
in and send immediately.

**Delete:** `POST /school/users/<id>/delete`

Hard-deletes the user row. **This destroys audit attribution** — past
audit events that referenced this user now point to a missing user ID.
Prefer terminate unless you genuinely need the row gone.

**Guards.** You cannot suspend, terminate, or delete yourself. You
cannot suspend, terminate, or delete the last active
`associate_admin` in your org — one admin must always remain, or the
school cannot manage itself and must contact the operator for
recovery.

**Password reset.** `POST /school/users/<id>/reset-password`

Sets a new temporary password. The user is notified. Same recovery
path as master's `/master/orgs/<id>/reset-password` — the difference
is that master uses it only as a last resort; you use it as ordinary
operation.

## 5.9 Templates

**List:** `GET /templates`

Message templates with name, body, department scope. Filtered by your
department + shared.

**Create:** `GET`/`POST /templates/new`

Fields: name, body. Department is set to your `current_user.department`
automatically.

Templates are bodies only — they do not pre-bind to a group or a
schedule. When composing a campaign, you can load a template into the
body field; the campaign's recipients are chosen separately.

**Edit / delete:** `GET`/`POST /templates/<id>/edit`,
`POST /templates/<id>/delete`

## 5.10 Billing

**Wallet:** `GET /billing/wallet`

Current balance, list of transactions (append-only ledger). Every SMS
send debits, every schedule reserve debits, every refund credits.
Transaction rows show reason, delta, balance after, reference, and
timestamp.

**Invoices:** `GET /billing/invoices`

Your org's invoices — paid, pending, cancelled. The PDF is
downloadable from the invoice detail.

**Buying a plan.** Self-service purchase is **not available today**
(backlog #43). You contact the operator to buy. They issue an invoice;
you pay by whatever method you agreed; the operator marks the invoice
paid in the master console; credits appear in your wallet. This is the
current model. Read `DEPARTMENTS.md` §2 for when this is expected to
change.

## 5.11 Settings — pool sharing

**Route:** `GET /settings`

This page exists for `associate_admin` with `department=None`.
Dept-scoped users can view it but the pool-sharing section is
disabled.

**Pool sharing.** Optional. If you enable pool sharing, your contacts
are copied into the master's contact pool. The operator can then send
campaigns to that pool — from the platform sender org, not from your
org — for campaigns that benefit the whole customer base (e.g. mobile
money outage notices, holiday hours, regional events).

**Enabling.** You are shown the pool agreement text (verbatim) and
must accept it. On acceptance:

- A `PoolPermission` row is created with the agreement text saved
  verbatim
- Your contacts are snapshotted into `PoolContact` rows with their
  group name, district, and source org ID at that moment

**What the snapshot means.** If you later rename a group, add contacts,
or delete a contact, the pool does not change — it holds the snapshot
from the moment you granted permission. To refresh the pool from your
current data, revoke and re-grant.

**Revoking.** `POST /settings/pool/revoke`. Deletes all `PoolContact`
rows with your `source_org_id`. Your own contact list is unchanged.
Revocation is immediate — future pool campaigns do not include your
contacts.

**Opt-outs propagate.** If a contact opts out via any path, the pool
entry is also marked opted out (`propagate_opt_out`). This is
non-negotiable — you cannot keep a contact in the pool after they've
opted out.

## 5.12 Chat

**Route:** `GET /chat`

Two channels:

- **DM with master** — your private channel with the platform
  operator. Use it for support, questions, or urgent issues.
- **Broadcast** — visible to all associates across all orgs. Use it
  for public questions or announcements. Master also posts here.

3-second polling. Read state per user per channel. No notifications
for new messages — the count in the sidebar is the indication.

## 5.13 Reports

**Route:** `GET /reports`

Delivery summaries — sent, delivered, failed, by date range and by
campaign. This is the place to investigate a specific campaign's
delivery status: how many delivered, how many failed, which
recipients failed and why.

Per-message detail is on the campaign detail page (§5.6), not here.

## 5.14 Notifications

**Route:** `GET /notifications`

Computed live from your org's state. Each notification corresponds to a
detected condition — low wallet balance, plan expiring soon, no
contacts, no campaigns sent recently, pending import to review.

You can dismiss each notification. The `NotificationDismissal` row
records that you've seen it; the notification does not reappear unless
the condition clears and recurs. There is no inbox — nothing is stored
to "keep up with." The notification list at any moment reflects the
current state of your org.

## 5.15 Profile

**Route:** `GET /profile`

Your own account — email, name, department (read-only, set by school
admin if you're dept-scoped), password change.

You cannot change your own department. If you need a department
change, the school admin does it from `/school/users/<id>/edit`. This
is by design: a user should not be able to expand their own visibility
scope.

## 5.16 Common tasks — quick reference

| Task | Path |
|---|---|
| Send a message to all contacts | `/campaigns/new` → standard mode → group = All |
| Send a message to one group | `/campaigns/new` → standard mode → group = <name> |
| Send personalized messages | `/campaigns/new` → personalized (CSV) mode |
| Schedule for next week | `/campaigns/new` → schedule mode → set days/times |
| Cancel a schedule | `/campaigns/schedules/<id>/cancel` |
| Edit a scheduled time | `/campaigns/schedules/<id>/edit` |
| Import new contacts | `/contacts/import` → CSV upload |
| Review a skipped import | `/contacts/imports/<id>` |
| Add a bursar | `/school/users/new` → role=user, department=bursar |
| Suspend a user | `/school/users/<id>/suspend` |
| Reset a user's password | `/school/users/<id>/reset-password` |
| Buy more SMS | Contact the operator (no self-service yet) |
| Enable pool sharing | `/settings` → pool section |
| Ask the operator a question | `/chat` → DM with master |

## 5.17 Known limitations

Open items that affect your daily use:

- **No self-service plan purchase (#43).** Every SMS purchase is a
  manual transaction with the operator. See `DEPARTMENTS.md` §2.
- **Campaign cancel does not refund un-sent segments (#16, deferred).**
  Once a campaign is queued and the debit is taken, cancelling stops
  further sends but does not return credits.
- **Deleting a group referenced by a schedule leaves an orphan
  `group_id` (#38).** The schedule still fires from a snapshot of the
  resolved recipients at create time, so sends are not lost, but the
  schedule's `group_id` points to a missing group. Cancel schedules
  before deleting the groups they reference.
- **`iso()` emits naive datetimes without `Z`.** Timestamps in the
  mobile API response are UTC but not explicitly timezone-tagged.
  This is a mobile-API-side issue; the web UI timestamps are correct.
- **Password-set link expires in 24 hours.** If you don't set your
  password in time, contact the operator for a fresh link.
- **Vertical has no UX effect yet (#51).** A business org and a school
  org look identical in the UI today. This will change when #51
  ships.

---

*Part 5 of 10. See `06-api-web.md` next.*