# Roman SMS

Multi-tenant bulk SMS reseller platform built on a single Pahappa Comms
(EgoSMS) master account. Associates buy credit plans, manage their own
contacts, and send under the Roman SMS master brand with a per-associate
body prefix.

## Status

Phases 0–4 are complete and verified. The platform is feature-complete
for its first paying client. Awaiting production API credentials from
Pahappa to enable live sends.

| Phase | Scope | State |
|---|---|---|
| 0 | Foundation, models, master seed | ✅ Done |
| 1 | Core sending, worker, wallet | ✅ Done |
| 2 | Master console, plans, subscriptions | ✅ Done |
| 3 | Billing, invoices, mark-paid | ✅ Done |
| 4 | Rate limits, opt-out, backups, logging | ✅ Done |
| + | Districts, master pool, chat, notifications, webhook | ✅ Done |
| 5 | Premium: registered sender IDs | Gated on paying client |

## Quick start

```bash
make install-dev          # venv + deps
cp .env.example .env      # fill in values (see below)
make seed                 # creates master, system org, admin, plans
python scripts/seed_districts.py   # reference data for districts
make run                  # http://localhost:5000

Log in with the values from .env (MASTER_EMAIL / MASTER_PASSWORD).
Architecture at a glance
text

Routes  ─┐
Worker  ─┼─▶  Services  ─▶  Models  ─▶  Postgres / SQLite
CLI     ─┘        │
                  └─▶  Pahappa Comms API   ─▶  Networks
                          ▲
                          │
                  Inbound webhook  ◀── Delivery reports

    Routes are HTTP glue.

    Services hold every business rule and are shared by routes, worker, and CLI.

    The worker drains a database-backed queue. No Celery, no Redis.

    Delivery reports arrive on our own webhook endpoint, not by polling.

Layout
text

app/
  routes/       HTTP handlers only
  services/     All business logic (shared by web, worker, CLI)
  models/       SQLAlchemy models
  templates/    Jinja templates
  permissions.py  Role decorators and org scoping
  cli.py        flask commands
docs/           Architecture, runbook, decisions, scope
scripts/        seed, backup, reconcile, migration helpers
tests/          Unit + integration
worker.py       Background queue drainer