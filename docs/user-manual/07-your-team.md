# 7. Your team — adding and managing staff

**Admin only.** If you are a staff member and not the school or
business administrator, you can skip this section. You can't see the
**School users** page and can't add anyone.

This section is for the person who runs your organization's Roman
SMS account — the school administrator or the business owner. It
covers creating staff logins, changing what they can see, and
removing their access when they leave.

## What a staff login is

Every person who uses Roman SMS gets their **own login**. There is
no shared account. This is deliberate:

- **Every message has an author.** When someone sends a campaign,
  the campaign record shows who created it. This matters if a
  message goes out that shouldn't have.
- **Departments can be scoped.** A bursar sees only bursar data. A
  DOS sees only DOS data. Nobody accidentally sends a bursar
  reminder to a DOS group.
- **Removing access is clean.** When a staff member leaves, you
  terminate their login. Nothing else changes.

A staff login is separate from a personal email or phone number.
Your staff log in with the email address you set up for them on
Roman SMS.

## Roles, briefly

Roman SMS has two roles you can assign to your staff:

- **Associate administrator** — full control of the organization.
  Can see all data, manage users, buy credits, add contacts and
  campaigns in any department. This is the same role you have (if
  you are reading this section, you are one).
- **User** — restricted to their own department's data plus shared
  records. Can send messages, manage contacts, but cannot manage
  other users or see billing.

**A third role — "associate administrator with a department" —
is not allowed.** The system won't let you create one. If you try,
the form rejects it. The reason: an administrator can see every
department's data, so scoping them to one department would be
inconsistent. If you want someone to have admin control, they get
everything. If you want them scoped, they're a regular user.

## What "department" means

A **department** is a scope for a staff member's visibility. If a
user is in the "bursar" department, they see:

- Their own department's contacts, groups, templates, campaigns,
  and schedules.
- Anything marked "shared" (created by you, the administrator, or
  by other departments if explicitly shared).
- **Not** other departments' items.

Departments are optional. A user with **no department** sees
everything in the organization — same visibility as an
administrator, just without the admin powers (no user management,
no billing).

For a school, common departments are **bursar**, **DOS** (Director
of Studies), **dean**, and **HT** (Head Teacher). For a business,
departments are less common — most businesses have every user
seeing everything.

If you're not sure whether a staff member needs a department:
**give them one**. It's easier to widen access later than to
narrow it after they've seen things they shouldn't have.

## Adding a staff member

**Admin only.**

1. Open the **School users** page in the left menu.
2. Click **New user** (top-right).
3. Fill in:
   - **Email** — the address they'll log in with. Use a real
     address the person can access, because the welcome email goes
     there.
   - **Full name** — their name. Shows in campaign records and
     audit trails.
   - **Password** — either type one now (they can change it later)
     or leave blank and let the system send them a set-password
     link. **Recommendation:** leave it blank. A set-password link
     is safer and takes no more effort.
   - **Role** — choose **User** for staff. Choose **Associate
     administrator** only if you want them to have full admin
     control.
   - **Department** — optional. Pick the department they belong to,
     or leave blank for full access (regular users only — admins
     always have full access regardless).
4. Click **Save**.

**What happens next:**

- If you set a password: the user gets a welcome email telling
  them their account is ready, but not their password. **You must
  tell them the password yourself** — in person, over the phone,
  or via another channel. Do not email it; email can be
  intercepted.
- If you left password blank: the user gets a welcome email with a
  link to set their password. The link expires in 24 hours.

`[SCREENSHOT: The New user form showing the department dropdown]`

### Why leaving password blank is better

Every login should be set by its owner, not by someone else.
When you leave the password blank:

- The user sets a password only they know.
- If it's intercepted, nothing happens — it's a password-set
  link, not a password.
- You never need to have a plaintext password on file or in your
  head.
- If the link expires before they use it, you can re-trigger it
  from the user detail page.

The only case where setting a password manually is better: the
user can't receive email at the address you're setting up for
them. That's rare. If it happens, set a temporary password, hand
it over securely, and ask them to change it on first login.

## Editing a staff member

**Admin only.**

1. Open **School users**.
2. Click the user's email address to open their detail page.
3. Click **Edit** (top-right).
4. Change what you need.

What you can change:

- **Name** — for display and audit purposes.
- **Email** — the login address. Careful: changing this changes
  their login. If they're currently logged in, they'll still be
  logged in until they log out, but next time they log in they
  need the new email.
- **Department** — moves them from one scope to another. Their
  existing records keep the old department; new records carry the
  new one.

What you **cannot** change:

- **Role.** A user created as a regular user stays a regular user
  until you delete and re-create them. See "Changing a user's
  role" below.

`[SCREENSHOT: A user detail page showing the activity summary]`

## Changing a user's role

You can't. Not through the edit form. The role is set at creation
and doesn't change.

**If you need to change someone's role**, the sequence is:

1. **Delete the existing user.** This loses the connection
   between the user and their past actions — anything they did
   (created campaigns, edited contacts, changed settings) will show
   in the audit log as having been done by a deleted user.
2. **Create a new user** with the new role. Send them a fresh
   welcome email.

This is a real limitation and we're aware it's inconvenient. It
exists because keeping a role change auditable (someone was a
regular user yesterday and an admin today) is more complex than it
looks. If you need this frequently, contact the operator — we can
help with a workaround, or note it as a feature request.

**Before you delete anyone**, read "Terminating vs. deleting" below
— deletion has real consequences.

## The user detail page

Click any user's email address on the School users page to open
their detail page. It shows:

- **Name, email, role, department** — the basics.
- **Status** — active, suspended, or terminated (see below).
- **Created date and last login** — when they were created and
  when they last used the system.
- **Campaigns (all-time)** — how many campaigns they've sent.
- **Campaigns (last 30 days)** — recent activity.
- **Active schedules** — schedules they created that are currently
  active.
- **Audit events** — every action they've taken that was recorded.
- **Recent campaigns** — the last 10 campaigns they created, with
  links to see the details.
- **Recent schedules** — the last 10 they created.
- **Recent audit activity** — the last 20 actions.

This page is the place to visit when you want to know "what has
this person been doing." It's read-only — nothing on this page
changes anything.

## Suspending, terminating, and deleting

Three distinct actions, each for a different situation. Don't
confuse them.

### Suspend

**What it does:** The user can still log in and see their data, but
cannot send new messages or create new campaigns. Existing
scheduled campaigns continue to fire on their behalf.

**When to use:** The user is on leave, on temporary restriction, or
under investigation — but you might reinstate them.

**How to suspend:** Open the user detail page, click **Suspend**,
confirm.

**To undo:** Click **Reactivate** on the same page.

### Terminate

**What it does:** The user cannot log in at all. They see an error
message saying their account is inactive. Any existing scheduled
campaigns they created continue to fire on their behalf (the
school's commitment to those sends stands).

**When to use:** The user has left the school or business
permanently and you want to fully revoke their access while
preserving the audit trail (their past actions still show their
name, not a deleted user).

**How to terminate:** Open the user detail page, click
**Terminate**, confirm.

**To undo:** Click **Reactivate** on the same page — this is
equivalent to creating a new active user with the same email and
history.

### Delete

**What it does:** Removes the user row entirely. The user cannot
log in, and their identity is gone from the system. **Historical
audit records that referenced this user now point to a missing
user ID.** Past campaigns they created show "unknown user" instead
of their name.

**When to use:** Rarely. Only when you genuinely need the row gone
— for example, a user created by mistake, or a duplicate account
you want cleaned up.

**How to delete:** Open the user detail page, click **Delete**,
confirm. This is a hard delete — no undo.

**Prefer terminate over delete** for actual users. Terminate
achieves the same security outcome (the person can't log in)
without destroying the audit trail.

### Comparison table

| Action | Can log in? | Can send? | Keeps history? | Undo? |
|---|---|---|---|---|
| **Suspend** | Yes | No | Yes | Yes (reactivate) |
| **Terminate** | No | No | Yes | Yes (reactivate) |
| **Delete** | No | No | No — history loses attribution | No |

## Guards — what you can't do

The system prevents three things, deliberately:

**You cannot suspend, terminate, or delete yourself.** This avoids
an accidental lockout. To remove your own access, ask another
administrator in your organization, or contact the operator.

**You cannot suspend, terminate, or delete the last active
administrator.** Your organization must always have at least one
administrator. If you're the only admin, you can't remove yourself
(see above). If you're one of several, you can remove another
admin as long as at least one remains.

**You cannot create an administrator with a department.** See
"Roles, briefly" earlier in this section.

These guards protect against the most common lockout scenarios.
They're not obstacles — they're the system doing its job.

## If you get locked out

If your organization loses access to all its administrators — for
example, the only admin left the school without handing over
access — you cannot fix this yourself. Contact the operator.

The operator can reset an existing administrator's password from
their master console. They cannot create new users (that's your
job), but they can restore access to an existing admin. This is
the recovery path.

**One thing that helps in advance:** have **two** active
administrators. One is a single point of failure. Two is a
safety margin. The second admin doesn't need to log in regularly
— they just need to exist so that password recovery is possible if
the primary admin is unavailable.

## Password resets

**Admin only.**

If a staff member forgets their password, you can reset it.

1. Open the user detail page.
2. Click **Reset password**.
3. Choose a new temporary password, or leave blank to send a
   reset link.
4. Click **Save**.

**If you set a temporary password:** Tell the user the password
via a secure channel — in person, over the phone, not email.
Ask them to change it on first login.

**If you send a reset link:** The user gets an email with a link
that expires in 24 hours. They click it and set their own new
password.

Password resets are routine. Nobody should feel embarrassed about
forgetting a password — it happens. Reset takes a minute.

## Common staff setup patterns

### Small school (3–5 staff)

- **You (administrator)** — full access, no department.
- **Bursar** — user role, bursar department. Handles fee reminders.
- **Head teacher** — user role, no department. Sees everything
  (same as admin, without user management).

Two admins is ideal, but if only you have full access, that's fine
as long as you have a secure way to recover if you're
unavailable.

### Larger school

- **You (administrator)** — full access.
- **Second admin** (vice principal, IT staff) — full access.
  Exists for recovery.
- **Bursar** — user role, bursar department.
- **DOS** — user role, DOS department.
- **Dean** — user role, dean department.
- **Head teacher** — user role, no department (sees all).
- **Teacher-senders** — user role, department = whatever class
  they manage.

### Business

- **Owner (administrator)** — full access.
- **Second admin** (manager, spouse, business partner) — full
  access. Exists for recovery.
- **Staff who send** — user role, no department. Most businesses
  don't need departments.

## If your team setup looks wrong

**"I can't see the School users page."** You're a user, not an
administrator. Ask your administrator to give you access — or if
you *are* the administrator and can't see it, contact the
operator. Something is wrong with your role.

**"I created a user but they never got the welcome email."** Check
the email address. If it's misspelled, edit the user and re-send.
If the address is right, ask the user to check their spam folder —
welcome emails from `no-reply@romansms.com` sometimes end up
there. If still nothing, reset their password — the reset link
arrives the same way.

**"A staff member is gone but their scheduled campaigns are still
firing."** This is by design. Their schedules continue to run — the
school committed to those sends when the schedules were created.
If you want to stop the sends, cancel each schedule individually
from **Campaigns → Scheduled**. Terminating the user does not stop
their schedules.

**"I can't delete a user — the button is greyed out."** Likely
causes: (a) the user is you; (b) the user is the last administrator;
(c) the user is still active and needs to be terminated first in
some older versions. Try terminating first, then delete.

---

*Section 7 of 10. See `08-billing.md` next.*