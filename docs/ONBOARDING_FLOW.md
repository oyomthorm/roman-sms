# Onboarding flow — verified end to end

The full customer journey from applicant → signed-up org with credits →
first sent campaign. Verified on 2026-11-13 against prod
(https://romansms.com) with a real signup and real email delivery.

This document lists what each step does, where the code lives, and what
could break. Use it when onboarding a new school or business, when
debugging a stuck signup, or when verifying that nothing regressed.

## The chain

    Applicant submits /signup
       |
       v
    SignupRequest created (status='pending')
       |
       v
    Applicant gets acknowledgement email
    Master gets notification email (ALERT_EMAIL)
    Master sees in-app notification
       |
       v
    Master reviews /master/signups/<id>
       |
       v
    Master selects vertical (school / business / unclassified) and
    clicks Approve with starter_credits
       |
       v
    Organization created (with vertical), admin User created
    Starter credits granted via wallet transfer from master
    SignupRequest.status = 'approved'
       |
       v
    Welcome email sent with password-set link
       |
       v
    Applicant clicks link → sets password → login
       |
       v
    Applicant sees dashboard with brand + starting wallet balance
       |
       v
    Applicant adds contacts (manual or CSV) or imports
       |
       v
    Applicant sends first campaign
       |
       v
    Campaign queued → sending → complete
    Wallet debited per segment
    Master sees audit entries for the whole chain

## What each step does

### 1. Applicant submits /signup

- **Route:** `app/routes/signup.py::index` (POST)
- **Service:** `services/signups.py::submit_request`
- **Creates:** one SignupRequest row. **Nothing else.**
- **Sends:** acknowledgement email to applicant, notification email to
  ALERT_EMAIL (master).
- **Validates:** company name, contact name, valid email, slug format
  (lowercase + dashes), brand name length ≤ 20, slug not already taken
  by a live org, email not already registered.
- **Idempotency:** duplicate submission from the same email returns the
  existing pending request instead of creating a new one.

### 2. Master notification email

- **Service:** `services/signups.py::_notify_master`
- **Recipient:** `ALERT_EMAIL` config (currently `oyomthorm.21@gmail.com`)
- **Delivery:** Mailgun on port 2525 (DigitalOcean blocks 25/465/587).
- **Content:** company name, contact info, slug, brand, expected volume,
  free-text message, review URL.

**If this fails:** check `journalctl -u roman-sms | grep -i mail`. See
RUNBOOK.md "SMTP configuration".

### 3. Master reviews and approves

- **Route:** `app/routes/master.py::signup_approve`
- **Service:** `services/signups.py::approve(req, *, actor,
  starter_credits=None, vertical=None)`
- **Creates:**
  - `Organization` (name, slug, brand, contact, district, **vertical**)
  - `User` (associate_admin, email = contact_email, password = random
    token, so applicant must set real password via welcome link)
  - Starter credits transferred from master wallet to new org wallet
    (default 100, configurable via `SIGNUP_STARTER_CREDITS`)
- **Updates:** SignupRequest.status = 'approved', reviewed_by, reviewed_at,
  created_org_id, created_user_id
- **Sends:** welcome email with password-set link
- **Rejects if:** slug taken, email registered, master org missing, request
  not pending.

**The vertical selection (#45):** the approve form includes radio buttons
for School / Business / Unclassified. The selected value is passed as
`vertical=` to `signups.approve`, which sets `Organization.vertical`.
Master can also change it later via `/master/orgs/<id>/edit`.

**If this fails:** the flash message names the specific failure
("Slug taken", "Email registered", "Request already approved"). The
transaction rolls back cleanly — nothing is created.

### 4. Welcome email and password-set

- **Service:** `services/signups.py::_send_welcome`
- **Token:** `services/password_reset.py::make_token(user, purpose='welcome')`
- **Recipient:** applicant's contact_email
- **Contains:** password-set URL (expires 24 hours), brand prefix
  preview, note about the starter credit grant.
- **Failure handling:** try/except around the mail send; a mail failure
  does not roll back the org/user creation. The admin can manually
  trigger a new password-reset email from `/master/orgs/<id>` (reset
  form) if the applicant never received the welcome link.

### 5. Applicant sets password and logs in

- **Route:** `app/routes/auth.py::reset_password` (GET + POST)
- **Validates:** token, expiry, new password rules
- **Updates:** `User.password_hash`
- **Then:** standard login flow — `POST /login`, session cookie set,
  redirect to dashboard.

### 6. Applicant's first campaign

- **Route:** `app/routes/campaigns.py::new`
- **Service:** `services/campaigns.py::create_campaign`
- **Debits:** wallet per total segments, before dispatch
- **Creates:** Campaign, MessageLog rows (one per recipient), SendQueue
  row
- **Worker:** claims the SendQueue row, calls Pahappa (EGOSMS), marks
  each MessageLog sent/failed, refunds failures.
- **Webhook:** Pahappa POSTs delivery reports to
  `/api/webhooks/egosms`, flipping MessageLog.status to `delivered` or
  `delivery_failed`.

## What could break, and how to check

| Step | Failure mode | Check |
|---|---|---|
| Signup form | Form 500s, validation rejects valid input | `journalctl -u roman-sms` after a submission |
| Ack email | Applicant gets nothing | Mailgun dashboard; `journalctl -u roman-sms` |
| Master notification | Master doesn't see new signups | Check `ALERT_EMAIL`; test with a real signup |
| Approve | Org created but user missing (or vice versa) | Transaction is atomic — either both or neither |
| Vertical not saved | Org shows NULL vertical | Check `Organization.vertical` column; test #45 unit tests still pass |
| Welcome email | Applicant never gets link | Try `/master/orgs/<id>` reset form; or check Mailgun |
| Login fails after password set | Password hash not updated | Run `flask shell` and check `user.check_password('...')` |
| First campaign stuck | Worker not running | `systemctl status roman-worker`; `journalctl -u roman-worker` |
| Campaign fails entirely | Pahappa API down | `journalctl -u roman-worker` for HTTP errors |

## Minimal end-to-end test (30 min)

1. Signup with a real email you control. Verify both emails arrive.
2. Master: approve with vertical=School and 10 starter credits.
3. Verify `Organization.vertical='school'` and `User.status='active'`
   via `python -c` on prod.
4. Click password-set link from the welcome email. Set password.
5. Log in. Verify dashboard shows brand + 10 credits.
6. Add a contact (or paste 1 number in a campaign).
7. Send a 1-recipient campaign. Verify queued → sending → complete.
8. Verify wallet went from 10 to 9 (1 segment).
9. Master: check `/master/audit` for `signup_submitted`, `signup_approved`,
   `campaign_queued`, `wallet_debit`.
10. Clean up: `/master/orgs/<id>` → Suspend. Or hard delete via shell
    (see RUNBOOK.md "Useful one-liners").

See the "onboarding flow verified 2026-11-13" session log in
START_STATEMENT.md for the exact steps that succeeded.

## What is NOT verified

- **USSD payment line in a personalized campaign** — feature deferred
  (#33 follow-up).
- **Different onboarding copy for school vs business** — deferred (#51);
  currently both get the same generic welcome email.
- **Self-service plan purchase** — master must assign; no self-serve
  (#43).
- **Multi-user onboarding** — signup creates one admin; the school
  invites other users via `/school/users` after first login. Not
  covered in this flow test.