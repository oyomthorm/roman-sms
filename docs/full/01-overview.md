# Part 1 — Overview

## 1.1 What Roman SMS is

Roman SMS is a **multi-tenant SMS reseller platform** built for Ugandan
schools and businesses. The operator (a single person or small team,
called the **master**) acquires bulk SMS credits wholesale from a
Ugandan gateway (Pahappa / EGOSMS) and resells them to schools and
businesses at a markup. Each school or business is an **associate
organization** — a paying client with its own users, contacts, and
wallet.

The platform's core value: a school's bursar can send fee reminders to
500 parents in one operation. A business can send a promotion to 2,000
customers. The operator earns the margin between wholesale and retail
pricing. Every SMS is billed, tracked, and refunded on failure.

The build is deliberately narrow. It does not do:

- Inbound SMS (one-way only)
- Voice calls
- Email marketing (email is used only for transactional notifications)
- Multi-currency (UGX only)
- Self-service signup without operator approval

The build does well:

- Contact management with CSV import and per-row error reporting
- Personalized message sends (per-recipient CSV merge)
- Scheduled recurring campaigns with credit reservation
- Department-level visibility isolation within a school
- Wallet ledger with strict integrity invariants
- Master console with full operator control

## 1.2 Who uses it

### 1.2.1 Master (platform operator)

One person — you, the operator. Logs in as `master_admin` (role). Full
platform control: create orgs, approve signups, assign plans, issue
invoices, grant credits, view audit log, send master pool campaigns
from the system sender identity.

**Master does NOT create school users.** That is the school admin's
job. The one exception: master resets a school admin's password if they
lose access.

### 1.2.2 Associate organization (school or business)

Each school or business is one **organization**. It has:

- A **brand prefix** — prepended to every SMS: `"BRAND: your message"`.
  Max 20 characters.
- A **wallet** — SMS credits in integer units (1 SMS = 1 segment = 160
  characters including the brand prefix).
- **Users** — typically a school admin + department-scoped staff
  (bursar, DOS, dean, HT), or a general business owner + staff.
- **Contacts** — recipients, organized in groups.
- **Campaigns** — the sends. Immediate or scheduled.

### 1.2.3 The two customer verticals

As of 2026-11-13, the platform serves two verticals:

- **Schools** (`organization.vertical = 'school'`) — the primary market.
  Users have departments (bursar, DOS, dean, HT). Each department sees
  only its own + shared groups/templates/campaigns/schedules.
- **Businesses** (`organization.vertical = 'business'`) — secondary
  market. No department semantics; every user sees everything.

The vertical field is **master-only** and set at signup approval. It does
not affect permissions or filters (yet). It exists for onboarding copy
and analytics.

## 1.3 Roles and permissions

Three roles, no permission tables:

| Role | Scope | What they can do |
|---|---|---|
| `master_admin` | Every org | Everything at the platform level. Does not create school users. |
| `associate_admin` | Own org | Full control of their org: users, contacts, groups, templates, campaigns, schedules, wallet, pool permission. Cannot create other orgs. |
| `associate_user` | Own org, department-scoped | Same as admin for data operations, but scoped by department. Cannot manage users or assign departments. |

See Part 9 (ADR-005) for why three roles and no permission tables.

## 1.4 The layers

    Routes  ┐
    Worker  ┼──▶ Services ──▶ Models ──▶ Postgres
    CLI     ┘        │
                     └──▶ Pahappa API ──▶ SMS network
              ▲
              │
    Webhook ──┘ (delivery reports)

**Routes** are HTTP glue. They validate form input, dispatch to a
service, and render or redirect. **No business rule lives in a route.**

**Services** contain every business rule. The worker and the CLI call
the same service functions. Nothing enforces a rule twice.

**Models** are SQLAlchemy classes. They define tables, fields,
relationships, and convenience properties. **No business logic in
models.**

**The worker** is a single Python process (`worker.py`) that:
- Claims due schedule rows and materializes them into campaigns
- Drains the send queue, calling Pahappa
- Runs two passes per tick: scheduler first, then queue drain
- No Celery, no Redis. Database-backed queue with `SELECT ... FOR
  UPDATE SKIP LOCKED`.

## 1.5 The technology stack

| Layer | Technology |
|---|---|
| Web framework | Flask 3.x |
| ORM | SQLAlchemy 2.x, Flask-SQLAlchemy |
| Migrations | Alembic (Flask-Migrate) |
| Auth | Flask-Login (session cookie), Bearer tokens for mobile |
| Forms / CSRF | Flask-WTF |
| Rate limiting | Flask-Limiter |
| Templates | Jinja2 |
| Database | Postgres 16 |
| Worker | Plain Python + systemd |
| Web server | Gunicorn behind Nginx |
| SSL | Let's Encrypt |
| Email | Mailgun SMTP (port 2525) |
| SMS | Pahappa Comms API (EGOSMS) |
| Hosting | DigitalOcean single VPS, Ubuntu 24.04 |
| Mobile | Flutter, Riverpod, go_router, Dio |
| CI/CD | Git push → manual pull on VPS (no CI pipeline) |

## 1.6 At-a-glance — the full system

**A single school's typical flow:**

1. **Signup.** School owner submits `/signup`. Master approves with
   `vertical='school'` and starter credits. Org + admin user created.
   Welcome email with password-set link.
2. **First login.** School admin sees dashboard, wallet balance, brand.
3. **Add contacts.** Manual or CSV import. Contacts organized into groups
   (e.g. "Form 1 Parents", "Class 6").
4. **Create templates.** Reusable message bodies with placeholders
   (`{{name}}`, `{{phone}}`).
5. **Send a campaign.** Choose group or district filter, or paste
   numbers. Message is rendered per recipient. Wallet is debited per
   segment. Worker dispatches via Pahappa. Delivery reports arrive via
   webhook.
6. **Schedule a recurring campaign.** For fee reminders every Friday.
   Credits reserved upfront. Fires every Friday. Cancel refunds.
7. **Add staff.** School admin creates bursar, DOS, dean, HT users via
   `/school/users`. Each sees only their department's data.

**A master's typical flow:**

1. Review and approve signups
2. Assign plans (Starter / Growth / Business / Scale / Enterprise)
3. Issue invoices, mark paid, grant credits
4. Monitor wallet balances, audit log, campaign activity
5. Send pool campaigns (cross-org consent-based sharing)

## 1.7 What this document covers

| Part | Subject |
|---|---|
| 1 | This overview |
| 2 | Architecture, tenancy, request flows, data model |
| 3 | Feature detail (A1-A5, #44, #45, #46, #47, #16, #33) |
| 4 | User guide — master console |
| 5 | User guide — school/business admin |
| 6 | API reference (web + mobile) |
| 7 | Services layer |
| 8 | Operations + working style |
| 9 | Architecture Decision Records (28 ADRs) |
| 10 | Appendices (test accounts, prod state, glossary) |

If you only read one part, read **Part 2** (Architecture). Everything
else assumes its vocabulary.

---

*Part 1 of 10. See `02-architecture.md` next.*