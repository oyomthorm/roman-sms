# Part 10 — Appendices

Reference material for finding things, not for understanding them. If
you are reading this to understand how Roman SMS works, you want Part
1 (Overview) or Part 2 (Architecture). If you are reading this to
find a specific fact, this is the right place.

## 10.1 Reading order and audience

The full document is 10 parts. Not every reader needs every part.

| Part | Title | Audience |
|---|---|---|
| 1 | Overview | Everyone — 15 minutes, read first |
| 2 | Architecture | Engineers, before touching any code |
| 3 | Features | Engineers and product — what shipped and why |
| 4 | Master console user guide | The platform operator |
| 5 | School/business admin guide | Customer administrators |
| 6a | Web route reference | Engineers — every HTML route |
| 6b | Mobile API reference | Mobile engineers — every JSON endpoint |
| 7a | Services layer | Engineers — every business rule location |
| 7b | Data model | Engineers — every table, every column |
| 8 | Operations | Whoever is on call |
| 9 | ADRs | Anyone about to challenge a design |
| 10 | Appendices | Reference lookups |

**If you are new:** Parts 1 → 2 → 3 → 5 in that order. That is: what
the platform does, how it's built, what shipped, and what an associate
sees.

**If you are onboarding as operator:** Parts 1 → 4 → 8 → 9. The master
console guide, the operations manual, and the decision history are
what a first week actually needs.

**If you are onboarding as engineer:** Parts 2 → 7a → 7b → 6a → 9.
Architecture, then services, then models, then the route surface, then
the reasons each design is the way it is.

## 10.2 Test accounts

### Production

| Email | Password | Role | Org |
|---|---|---|---|
| `admin@romansms.local` | `ChangeMe123!` | master_admin | 1 (roman-sms) |
| `oyomthorm.21@gmail.com` | *(set by user)* | associate_admin | 3 (fitting) |
| `associate@romansms.com` | `Temp2026!` | associate_user | 4 (tasms) |
| `oronek1984@gmail.com` | *(set by user)* | associate_admin | 5 (orsms) |

**All shared passwords must be changed before production customers
are onboarded.** The `Temp2026!` on the associate test account is
documented here only so the operator can log in as the associate to
verify a support claim; it is not a credential for third parties.

### Local development

| Email | Password | Role | Org |
|---|---|---|---|
| `admin@romansms.local` | `ChangeMe123!` | master_admin | 1 (roman-sms) |
| `admin@test.com` | *(from seed)* | master_admin | 1 (roman-sms) |
| `oyomthorm.21@gmail.com` | *(from seed)* | associate_admin | 3 (roman-computer-services) |
| `associate@romansms.com` | `TempAssociate2026!` | associate_user | 5 (tasms) |

**The local `associate@romansms.com` password differs from prod.** Local
is `TempAssociate2026!`, prod is `Temp2026!`. Org IDs also differ
between local and prod — `tasms` is org 5 locally but org 4 in prod.

## 10.3 Production state (as of 2026-11-13)

### Infrastructure

| Item | Value |
|---|---|
| Provider | DigitalOcean |
| Droplet | `ubuntu-s5-2vcpu-4gb-30gb-mkc1` |
| IP | 165.245.199.37 |
| OS | Ubuntu 24.04 |
| Database | Postgres 16 |
| App root | `/srv/roman-sms/` |
| User | `oyomthorm` |
| SSH | passwordless (key auth) |
| sudo | still prompts — use `ssh -t` |
| SSL | Let's Encrypt, auto-renew via certbot |

### systemd units

| Unit | Status | Purpose |
|---|---|---|
| `roman-sms.service` | active | Gunicorn, 3 workers, 127.0.0.1:8000 |
| `roman-worker.service` | active | Scheduler + send queue |
| `roman-panel.service` | active | Flask ops panel, 127.0.0.1:8080 |

### Organizations in production

| ID | Slug | Vertical | Notes |
|---|---|---|---|
| 1 | `roman-sms` | NULL | Master org |
| 2 | `roman-platform` | NULL | System sender (pool campaigns) |
| 3 | `fitting` | `school` | **Real customer.** Schedule #1 fires through 2026-11-29 |
| 4 | `tasms` | NULL | Test org (TempAssoc), 166 contacts |
| 5 | `orsms` | `business` | **Real customer** (ORONEK), 0 contacts |

### Users in production

| Email | Org | Role | Status |
|---|---|---|---|
| `admin@romansms.local` | 1 | master_admin | active |
| `oyomthorm.21@gmail.com` | 3 | associate_admin | active |
| `associate@romansms.com` | 4 | associate_user (dept=None) | active |
| `oronek1984@gmail.com` | 5 | associate_admin (dept=None) | active |

### Backups

| Path | Purpose |
|---|---|
| `/srv/roman-sms/backups/` | Daily cron, 03:00 UTC, schema only |
| `/srv/roman-sms/backups/pre_department_2026_11_09.sql` | Pre-department rollback backup (508 KB, 28 tables, verified) |

### SMTP

| Setting | Value |
|---|---|
| Provider | Mailgun |
| Port | **2525** (DigitalOcean blocks 25/465/587 permanently) |
| Domain | `mg.romansms.com` (verified) |
| From | `no-reply@romansms.com` |

### Deployed state

| Item | Value |
|---|---|
| Deployed SHA | `88adc6c` (pre-documentation) |
| Migration head | `87cd66d8578c` |
| Test count | 247 passing |

## 10.4 Migration chain

Seven revisions, linear:

    5e5fea16ea4e (base)
      +-- 00404835aeb7
          +-- 6c7a338d1274  (Contact.group_id NOT NULL, ContactImport.skipped_no_group)
              +-- e5997cc4f270  (A1: 5 department columns)
                  +-- c41928d919da  (#44: campaign_schedule.credits_reserved)
                      +-- e37cc1348332  (#46: user.status, user.status_changed_at)
                          +-- 87cd66d8578c  (#45: organization.vertical)  ← HEAD

Verify with `flask db current` before any deploy that touches models.
Never edit a live revision. Migrations are forward-only in practice.

## 10.5 Repository layout

    D:\Dev_Apps\roman_sms\
      app/                 Flask application (all source)
      docs/                Every .md doc — NOT at repo root
      docs/full/           This document (source parts 00–10)
      migrations/          Alembic — versions/ has the chain
      mobile/              Flutter client
      scripts/             One-off ops scripts
      tests/               pytest — unit/ + integration/ + fixtures/
      deploy/              systemd units, nginx, env example
      config.py            Env-driven config classes
      wsgi.py              WSGI entrypoint

**Docs live in `docs/`, not the repo root.** A bare `BACKLOG.md` at
root is a stray — never commit it.

### `app/` subdirectories

| Path | Contents |
|---|---|
| `app/__init__.py` | `create_app()` factory, blueprint registration |
| `app/extensions.py` | `db`, `login_manager`, `csrf`, `migrate` singletons |
| `app/errors.py` | Error handlers (HTML + JSON) |
| `app/logging_config.py` | Text or JSON logging |
| `app/permissions.py` | `master_required`, `org_admin_required`, `org_scoped` |
| `app/cli.py` | 16 CLI commands |
| `app/models/` | 12 modules, 25 `db.Model` classes |
| `app/services/` | 31 modules (business rules) |
| `app/routes/` | 18 HTML blueprints |
| `app/api/v1/` | 12 JSON modules (mobile API) |
| `app/templates/` | Jinja2 templates (46 files) |
| `app/static/` | CSS/JS |

### `docs/` subdirectories

| Path | Contents |
|---|---|
| `docs/*.md` | The living project docs (ARCHITECTURE, BACKLOG, DEPLOY, etc.) |
| `docs/full/*.md` | This document (source parts) |
| `docs/Roman_SMS_Full_Documentation.docx` | This document, pandoc-built |

## 10.6 Glossary

Terms used across this document, with the specific meaning they carry
in this codebase — some are close to their generic meaning, some are
not.

| Term | Meaning in this codebase |
|---|---|
| **Organization / org** | A tenant. Every tenant-scoped table has an `org_id`. There are three kinds: master, system, associate. See §2.2. |
| **Master org** | Org 1. The platform operator's org. `is_master=True`. Only member sees cross-org data. |
| **System org** | Org 2. Internal sender identity for pool campaigns. `is_system=True`. Invisible to associates. |
| **Associate** | A paying customer. Org with `is_master=False, is_system=False`. Called "school" or "business" depending on vertical. |
| **Vertical** | School / business / NULL. Master-only classification on `organization.vertical`. No behavioral effect today — see ADR-025. |
| **Department** | A user-scoped visibility filter on 5 tables. Values: `bursar`, `dos`, `dean`, `ht`, or `NULL`. `department=NULL` sees everything; a dept-scoped user sees own-dept + shared. See ADR-026. |
| **Shared record** | A record with `department=NULL`. Visible to every user in the org. |
| **Plan** | A subscription product. Price, credits, validity, rate limits. Immutable once issued. See §7b.3. |
| **Subscription** | A plan instance for one org. Snapshots the plan at issue time. Expired and renewed by invoice. |
| **Invoice** | A request for payment. Snapshots plan at issue time. The PDF reads the invoice row alone — no live lookups. |
| **Wallet** | An org's credit balance. Not a stored integer — computed as `SUM(delta)` over the ledger. |
| **Ledger / wallet_transaction** | Append-only table of every credit and debit. `balance_after` cached for O(1) reads. |
| **Credit** | A positive wallet delta. Must have either `source_org_id` (internal transfer) or a reason from `EXTERNAL_CREDIT_REASONS`. See ADR-018. |
| **Debit** | A negative wallet delta. Always has a `reference` linking it to the triggering event (`campaign:123`, `schedule:45`). |
| **Reservation** | Pre-debited credits on a schedule. Stored in `campaign_schedule.credits_reserved`. `NULL` = legacy pre-#44 behavior. See ADR-023, ADR-027. |
| **Pool** | A cross-org contact database assembled from associates who opted in. Snapshot semantics. See §7b.7. |
| **Opt-out** | Platform-wide. A phone that opts out against any org is opted out against every org. `propagate_opt_out()` touches every entry. |
| **Segment** | One 160-character (GSM-7) or 70-character (UCS-2) piece of an SMS. Billing unit. Cost = sum of per-recipient segments. |
| **Brand prefix** | The `BRAND: ` string prepended to every message. Counts toward the segment total. Max 20 chars. |
| **Single-write-gate** | The pattern that writes are gated on all guards passing. See ADR-028, §8.7. |
| **Route blueprint** | A Flask blueprint. There are 18 HTML blueprints and 12 API modules. |
| **Service** | A module in `app/services/` holding business rules. Every route, worker, and CLI calls a service; no rule lives outside. |
| **MessageLog** | The per-recipient send record. `body` is the final rendered text (post-personalization). `status` moves through pending → sent → delivered (or failed variants). |
| **Dispatch** | The worker loop that claims queued campaigns, enforces rate limits, calls Pahappa, and updates MessageLog. |
| **Materialize** | The worker's act of turning a due schedule into a Campaign and MessageLog rows. See `schedules.materialize_run`. |
| **Claim** | A `SELECT ... FOR UPDATE SKIP LOCKED` against `send_queue` or `campaign_schedule` to reserve a row for this worker. |
| **Idempotency-Key** | A client-supplied header on mobile `POST /api/v1/campaigns` to prevent duplicate sends on retry. Stored in `api_idempotency`. |
| **Recipient resolution** | The step that turns "group + district + filters" into a list of contacts. Applied at create_campaign time and again at materialize time. |
| **Pahappa / EgoSMS** | The upstream SMS provider. Pahappa is the company; EgoSMS is the product. Used interchangeably in code. |
| **Mailgun** | The SMTP provider. Port 2525 — DO blocks standard ports. |
| **On-call** | Whoever is running the platform. Has access to prod SSH, master console, and this document's Part 8. |

## 10.7 Quick lookup — common tasks

| I want to… | Where |
|---|---|
| Deploy a new SHA | §8.2 |
| Roll back a deploy | §8.2 (Rollback) |
| Check prod state | §8.6 (`flask info`) |
| Add credits to an org | §4.6 (master console) |
| Recover a lost admin password | §8.6 (`flask reset-password`) |
| Read a stack trace | `journalctl -u roman-sms -n 200` |
| Stop the worker | `sudo systemctl stop roman-worker` |
| Inspect the wallet ledger | §7a.2, §7b.6 |
| Add a new service | §7a.33 |
| Add a new model | §7b.16 |
| Add a new HTML route | §6a.23 |
| Add a new mobile endpoint | §6b.17 |
| Change a plan | §4.7 (create new, don't edit) |
| Understand why something is odd | Part 9 (ADRs) |
| Find a form field name | `[VERIFY]` markers in Part 6, or read the template |

## 10.8 What this document does not cover

Four categories, each deliberately omitted:

**1. Legal documents.** The associate agreement, the pool consent text,
the privacy policy — these exist as text and are stored on
`PoolPermission.agreement_text`. Their *content* is not in this
document; their *mechanism* is (`§4.9`, `§7a.17`). If you need to know
what a customer agreed to, read the database row.

**2. Design assets.** Logos, color palette, typography choices. The
web UI uses Tailwind utility classes; the mobile UI uses Flutter
Material. Neither design language is documented here as a system.

**3. Historical context before 2026-10-01.** ADR-001 is the earliest
decision record. Pre-launch decisions that never became ADRs are not
in this document. If they matter, they matter only through their
consequences, and their consequences are visible in the current code.

**4. Marketing and sales collateral.** Pricing rationale, target
customer profile, competitive positioning. The *mechanics* of billing
are documented (§4.8, §7a.3); the *strategy* is not.

**Also not covered:** row data, WAL, PITR, off-site backup. This is a
documentation and architecture reference, not an operations log or a
data recovery plan. For backup state, see §8.3 and §10.3.

## 10.9 Where to update this document

If you change something the document describes, the document must be
updated in the same commit. Otherwise it lies. Specifically:

| Changed | Update |
|---|---|
| A route, endpoint, or permission | Part 6a/6b, and `docs/PERMISSIONS.md` |
| A model, column, or migration | Part 7b, and `docs/STRUCTURE.md` |
| A service function signature | Part 7a |
| A design decision | Part 9 (new ADR, or amend existing) |
| Prod state (orgs, SHAs, test count) | Part 10 §10.3 |
| The deploy procedure | Part 8 §8.2, and `docs/DEPLOY.md` |
| A backup schedule or path | Part 8 §8.3 |

**The `[VERIFY:]` markers in Parts 6 and 7 are the exception.** Those
are known gaps — points where the source file names something without
giving its type or field list. If you resolve one, delete the marker;
do not replace it with a guess. Guesses are worse than markers,
because markers are honest and guesses look like truth.

## 10.10 Version history

This document is regenerated by pandoc from `docs/full/*.md`. The
current `.docx` reflects all parts through Stage 6. Stage 7 (this part)
was the last. The generation command:

    pandoc docs/full/00-title.md docs/full/01-overview.md `
           docs/full/02-architecture.md docs/full/03-features.md `
           docs/full/04-user-guide-master.md docs/full/05-user-guide-school.md `
           docs/full/06-api-web.md docs/full/07-api-mobile.md `
           docs/full/08-services.md docs/full/08b-models.md `
           docs/full/09-operations.md docs/full/10-adrs.md `
           docs/full/11-appendices.md `
           -o docs/Roman_SMS_Full_Documentation.docx `
           --toc --toc-depth=3 --from=markdown --to=docx

**Do not use a glob** (`docs/full/*.md`). The glob picks up files that
are not parts of the intended document if any exist — a scratch file,
a draft, an editor backup. The explicit list is longer to type and
shorter to debug. This is ADR-028 applied to documentation: an explicit
manifest beats an implicit one.

To regenerate after edits:

    cd D:\Dev_Apps\roman_sms
    $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [Environment]::GetEnvironmentVariable("PATH", "User")
    pandoc docs/full/00-title.md docs/full/01-overview.md docs/full/02-architecture.md docs/full/03-features.md docs/full/04-user-guide-master.md docs/full/05-user-guide-school.md docs/full/06-api-web.md docs/full/07-api-mobile.md docs/full/08-services.md docs/full/08b-models.md docs/full/09-operations.md docs/full/10-adrs.md docs/full/11-appendices.md -o docs/Roman_SMS_Full_Documentation.docx --toc --toc-depth=3 --from=markdown --to=docx

Then commit both `11-appendices.md` and `Roman_SMS_Full_Documentation.docx`
together, with a message naming what changed. A `.docx` regeneration is
a documentation change and belongs in git like any other.

---

*Part 10 of 10. End of document.*