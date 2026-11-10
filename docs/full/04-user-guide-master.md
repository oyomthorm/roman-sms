# Part 4 — Master console user guide

This guide is for the **platform operator** — the `master_admin` user of
the master organization (org 1, slug `roman-sms`). If you are a school
or business administrator, read Part 5 instead.

The master console is mounted at `/master` and contains twenty-five or
more handlers, all gated by `@master_required`. It is the only place
where cross-org data is visible; every other page is scoped to the
logged-in user's own org.

## 4.1 What master can do that no one else can

From `docs/PERMISSIONS.md`, the actions exclusive to `master_admin`:

- Create, edit, suspend an associate organization
- View and approve signup requests (with vertical selection)
- Grant credits to any org from the master org's wallet
- Create and edit plans
- Issue invoices and mark them paid
- View every org's wallet, invoices, and user list
- View the master contact pool and send pool campaigns
- View and fund the platform sender org
- View the audit log

Everything else — sending campaigns, managing contacts, using chat — is
available to associates too. Master's advantage is *reach*: master sees
every org, associates see one.

## 4.2 The master dashboard

**Route:** `GET /master` (or `/master/`)

The master dashboard is the entry point. It is distinct from the
associate dashboard at `/dashboard` — a master user hitting
`/api/v1/dashboard` today gets **master-org stats**, not a cross-org
rollup (this is a known issue; see "Known limitations" below).

The dashboard shows, at minimum:

- Total organizations (excludes system orgs)
- Total active associate users
- Recent signup requests (pending count, if any)
- Wallet balance of the master org (used for granting credits)
- Recent audit events from across all orgs

## 4.3 Organizations — list, create, edit

**List:** `GET /master/orgs`

Every organization, with columns for slug, name, wallet balance,
active subscription, vertical (school/business/NULL), and created date.
The system org (Roman Platform, `is_system=True`) is invisible to
associates but visible here to the master.

**Create:** `GET`/`POST /master/orgs/new`

Creating an org directly (not through signup) is for internal use. The
normal flow is signup → approval, which sets up org + initial admin +
welcome email atomically. Manual creation is for edge cases: a customer
you're onboarding by phone, a demo org, a test org.

**Edit:** `GET`/`POST /master/orgs/<id>/edit`

Editable fields: name, slug, contact email, phone, address, the
`vertical` field (school / business / NULL — master-only), and the
active/inactive flag. Slug edits affect URLs but not login.

**Protected orgs.** `orgs._refuse_if_protected` blocks all writes to the
master org and the system org. Attempting to edit org 1 or org 2 from
the form returns an error. These orgs exist for platform mechanics —
master for granting credits, system as the sender identity for pool
campaigns — and must not be renamed, restyled, or deactivated.

## 4.4 The signup queue — approve or reject

**List:** `GET /master/signups`

Every `SignupRequest` with status `pending`, `approved`, or `rejected`.
Filtered by status by default to pending.

**Detail + approve:** `GET`/`POST /master/signups/<id>`

Each pending request shows: applicant name, organization name, slug
requested, email, phone, address, vertical (from the signup form — may
be NULL), submitted timestamp.

Approving performs a transaction with three writes:

1. `Organization` row created with `vertical` set to whatever master
   selects at approval time (school, business, or NULL)
2. `User` row created with role `associate_admin`, random password hash
   (user must set a real password via the email link)
3. `wallet_svc.transfer(master_org.id, new_org.id, starter_credits)` —
   the opening balance, counted as a `master_topup` in the audit trail

Then the request flips to `approved`, and a welcome email is sent to the
applicant with a password-set link that expires in 24 hours.

**Vertical selection at approval.** Master picks school, business, or
neither. If the applicant requested a vertical, it's preselected. If
not, master decides. This field is inert today — nothing in the
permission system or filters depends on it — but it records intent and
will drive onboarding copy once #51 ships. Set it correctly now.

**Rejecting.** Same page, "Reject" button. Sets status `rejected`. No
org or user is created. No email is sent unless you type a reason
manually — the current flow has no rejection-email step.

## 4.5 User management on an org

**Route:** `GET /master/orgs/<id>` — org detail, with the Users table

Master can see every user across every org, but per Q1 (in
`docs/DEPARTMENTS.md`) **master does not create school users.** That is
the school admin's job (Part 5, §5.7). Master's only user-level action
on a school org is **password reset** — used when a school loses access
to its admin and needs help recovering.

**Password reset:** `POST /master/orgs/<id>/users/<uid>/reset-password`

Master enters a new temporary password, and the user is emailed a
notification. The user then logs in and changes it via `/profile`.
This is the recovery path when the school's admin has forgotten their
password and there is no second admin.

**Why not create users.** The design decision is explicit: schools
manage their own people. If master could create users, it would blur
the boundary between the operator and the customer. A school that
loses all admins triggers a password reset, not a new user by master.

## 4.6 Wallet and credit grants

**Viewing any org's wallet:** `GET /master/orgs/<id>`

The org detail page shows current balance, recent transactions, active
subscription (plan, credits remaining, expiry), and invoice history.

**Granting credits:** `GET`/`POST /master/orgs/<id>/grant`

Form fields: amount (integer), reason (dropdown from
`wallet.EXTERNAL_CREDIT_REASONS` — `master_topup` is the standard),
notes (free text). Submitting calls
`wallet_svc.credit(org.id, amount, source_org_id=master_org.id,
reason='master_topup')`. The wallet's transaction list shows the grant
with `source_org_id=1` and the notes.

**Funding the master org itself:** `flask fund-master <amount>` — CLI
command. Used to seed the master wallet before granting to associates.
Not exposed in the web UI.

**Funding the platform org:** `flask fund-platform <amount>` — CLI. The
platform sender org (`is_system=True`) is debited when a pool campaign
is sent. Its wallet must have balance before the campaign fires.

## 4.7 Plans

**List:** `GET /master/plans`

Every plan with name, price, credit count, validity period, and
`max_per_minute` / `max_per_day` rate limits.

**Create:** `GET`/`POST /master/plans/new`

Fields: name, description, price (UGX), credits, validity days, max
per minute, max per day. Plans are immutable once issued to a
subscription — if you need to change a plan, create a new one and
migrate the customer with a new invoice.

## 4.8 Invoices — issue and mark paid

**List:** `GET /master/invoices`

Every invoice across every org, with status (`pending`, `paid`,
`cancelled`), amount, plan snapshot, and issuing org.

**Issue:** `GET`/`POST /master/orgs/<id>/new_invoice`

Creates an invoice for a specific org and plan. The plan's price and
credits are snapshotted into the invoice row so that later plan edits
don't change what the customer was charged.

**Mark paid:** `POST /master/invoices/<id>/mark-paid`

This is the transaction that grants the customer credits and starts the
subscription:

1. Any existing subscription for the org is set to `expired`
2. A new `Subscription` row is created from the invoice snapshot
3. `wallet_svc.credit(org.id, invoice.credits, source_org_id=master_org.id,
   reason='plan_grant')`
4. Invoice status becomes `paid`

The PDF is generated from the invoice row alone — no live Plan or Org
lookup — so the PDF that was issued today is still correct a year from
now even if the plan or org has changed.

**PDF export:** `GET /master/invoices/<id>/pdf`

## 4.9 The contact pool

**List:** `GET /master/pool`

The pool is a cross-org contact database built from associates who have
opted in. Each pool contact carries a snapshot of the group name,
district, and source org ID at permission time — so if a pool contact's
source group is later renamed or deleted, the pool entry stays stable.

Filtering: by district, by group, by source org.

**Granting / revoking permission:** this is done **on the associate's
side**, not from master. The associate navigates to `/settings` and
enables pool sharing (Part 5, §5.11). Master cannot grant or revoke on
their behalf — the agreement text must be accepted by the associate.

**Sending a pool campaign:** `POST /master/pool/send`

Compose a message; target pool contacts by filter; submit. The campaign
is sent from the **system sender org** (`is_system=True`), which is why
the platform org's wallet needs balance. Recipient opt-outs are
respected — every opt-out entry calls `propagate_opt_out(phone)` which
touches both `OptOut` and `PoolContact` rows.

## 4.10 Chat

**Route:** `GET /chat`

Chat is available to both master and associates, but the topology
differs:

- **Associates** see a DM channel with master, plus a broadcast channel
  visible to all associates.
- **Master** sees one DM channel per associate, plus the broadcast
  channel.

3-second polling refreshes the message list while the page is open. No
websockets. Read state is tracked per user per channel.

## 4.11 The audit log

**Route:** `GET /master/audit`

Every `AuditLog` row across every org, with filter by actor, action,
target, and date range. Actions include user creation, status changes,
wallet grants, plan assignments, schedule creation, invoice marking,
and password resets.

`AuditLog` is append-only — no rows are ever deleted or updated.
`audit.log()` commits its own transaction and swallows exceptions
(known issue — see §4.13), so if the audit write fails, the calling
action still succeeds. The trade-off is that audit is best-effort,
not transactional.

## 4.12 Settings and profile

**Master's own profile:** `GET /profile` — email, name, password change.

**Changing a master's password:** via `/profile`, or via CLI
`flask reset-password <email>` as a recovery path. The CLI reset is
used when a master is locked out — it generates a new random password
and prints it.

## 4.13 Known limitations

The following are open items in `docs/BACKLOG.md` that affect the
master console's behavior. They are documented here so you know the
current state, not as instructions to work around them:

- **Master org users hitting `/api/v1/dashboard` get master-org stats.**
  The mobile endpoint does not aggregate cross-org. If you open the
  mobile app as a master user, you see the master org's numbers, not
  the platform total. Workaround: use the master panel at `/master` for
  aggregate views; use the mobile app only for messaging.
- **`audit.log()` commits its own transaction.** A failed audit write
  does not roll back the business action. If audit completeness is
  required for a specific action, wrap the caller in an outer
  transaction and verify the audit row exists after.
- **No self-service plan purchase (#43).** Associates contact you to
  buy. Every credit is granted by you, every invoice is issued by you.
  See `DEPARTMENTS.md` §2 for when this needs to change.
- **Vertical selection has no effect yet (#51).** The field is set
  correctly at approval but nothing downstream branches on it. When
  #51 ships, onboarding copy and default screens will vary by vertical.
- **No screen to edit a master user's own email.** Use CLI
  `flask reset-password` for password recovery. Email changes go
  through SQL — there is no supported path today.

## 4.14 The master workflow — a first-time walkthrough

If you are new to being the operator, this is the sequence for
onboarding a new customer:

1. **Signup arrives.** Applicant submits `/signup`. You get an email at
   `ALERT_EMAIL`. The pending request appears at `/master/signups`.
2. **Review the request.** Click through to `/master/signups/<id>`. Check
   that the slug is free, the email is valid, and the vertical is
   appropriate. If the applicant mis-typed their organization name,
   reject and ask them to resubmit — do not approve with the wrong
   details and edit after.
3. **Approve.** Select vertical (school / business / NULL), set starter
   credits (usually 0 unless you're onboarding with a free trial), submit.
   Org and initial admin user are created atomically. Welcome email goes
   out with a password-set link.
4. **Wait for the password-set link.** If the applicant doesn't set
   their password within 24 hours, the link expires. Contact them to
   request a fresh link (you can trigger the reset email again from
   `/master/orgs/<id>` — see §4.5).
5. **Invoice and plan.** Once the customer is ready to buy, issue an
   invoice at `/master/orgs/<id>/new_invoice`, choose a plan, submit.
   PDF is downloadable immediately.
6. **Mark paid when payment arrives.** Bank transfer, mobile money, or
   however they pay — when you see the funds, mark the invoice paid at
   `/master/invoices/<id>/mark-paid`. This debits the master org, credits
   the associate, and starts the subscription.
7. **The customer sends.** From this point on, the customer's actions
   are governed by their plan's rate limits and their wallet balance.
   You are called in for top-ups, overrides, or problems.

---

*Part 4 of 10. See `05-user-guide-school.md` next.*