# Part 8 — Operations

Deploy, backup, SMTP, incident response, CLI verification, and the
working style that produced this document. This is the reference for
running Roman SMS in production — the paragraph you open at 02:00
when something is wrong.

## 8.1 Production topology

    DigitalOcean droplet ubuntu-s5-2vcpu-4gb-30gb-mkc1
    IP: 165.245.199.37
    OS: Ubuntu 24.04
    DB: Postgres 16
    DNS: romansms.com, mg.romansms.com (Mailgun)

    App root: /srv/roman-sms/
    User: oyomthorm
    SSH: passwordless (key auth); sudo still prompts
    SSL: Let's Encrypt via certbot

### systemd units

Three units, all `enabled` and `active` in production:

| Unit | What it runs | Bind |
|---|---|---|
| `roman-sms.service` | Gunicorn, 3 workers | 127.0.0.1:8000 |
| `roman-worker.service` | `worker.py` (scheduler + send queue) | none |
| `roman-panel.service` | Flask ops panel | 127.0.0.1:8080 |

Gunicorn binds to `127.0.0.1:8000`; nginx proxies `https://romansms.com`
to it. The panel on `127.0.0.1:8080` is not exposed publicly — reach it
via SSH port forwarding or nginx location restriction.

### Nginx

Reverse-proxies `romansms.com` (and `www.`) to the Gunicorn socket.
Handles HTTPS termination and the `X-Request-ID` header pass-through
to Flask. SSL certs auto-renew via certbot's systemd timer.

## 8.2 Deploy — the standard procedure

The procedure changed with the `wip/mobile-api` branch and the "pinned
revision" model. There is one procedure now:

    # 1. SSH to prod
    ssh oyomthorm@165.245.199.37
    # (for anything needing sudo, use -t)
    # ssh -t oyomthorm@165.245.199.37

    # 2. Update the pinned SHA
    cd /srv/roman-sms
    git fetch origin
    git rev-parse --short origin/wip/mobile-api   # confirm the target SHA
    git checkout <target-sha>                     # NOT a branch; a SHA

    # 3. Activate venv, install any new deps
    source venv/bin/activate
    pip install -r requirements.txt               # only if requirements changed

    # 4. Migrate (if migrations changed)
    flask db upgrade
    flask db current                              # verify head

    # 5. Restart the units
    sudo systemctl restart roman-sms roman-worker roman-panel
    sleep 2

    # 6. Verify
    systemctl is-active roman-sms roman-worker roman-panel
    # Expected: active / active / active

    curl -sf https://romansms.com/health && echo "OK" || echo "FAIL"
    # (or: curl -I https://romansms.com/ and check status)

**Why SHA-checkout, not branch-checkout.** The branch `wip/mobile-api`
is a moving target. Checking out the branch on prod means the next
`git pull` moves prod to whatever the branch is currently at — including
a commit that failed tests, or a partial push. Checking out a specific
SHA (verified on GitHub to be tested and deployed) makes prod
reproducible and inspectable. `git rev-parse HEAD` on prod tells you
exactly what is running.

**Migration discipline.** `flask db current` before and after
`flask db upgrade`. A deploy that runs the app against a stale schema
fails at the first query touching a missing column — usually not
during startup, but on a user request. Check head:
`87cd66d8578c` is the current production head.

**Rollback.** To roll back: `git checkout <previous-sha>`, then
`systemctl restart` the three units. **Do not roll back migrations**
unless the new code is genuinely incompatible with the old schema —
the down() paths exist but are not tested in production. If a
migration must be rolled back, take a backup first (see §8.3).

## 8.3 Backup

**Daily cron at 03:00 UTC**, schema only. Backups live at:

    /srv/roman-sms/backups/

Filename pattern: `backup_YYYY_MM_DD.sql`. Schema-only means the
backup contains `CREATE TABLE`, `CREATE INDEX`, and constraint
definitions but **not row data**. This is a deliberate trade-off: full
data backup would be tens of MB/day; schema backup is small, and the
data is recoverable from the live Postgres if the disk holds. A disk
loss recovery is not covered by this backup schedule — see "not
covered" below.

**Pre-migration backups.** Before any migration that alters the schema
destructively (dropping a column, changing a type), take a manual
full-data backup:

    pg_dump -U roman -Fc roman_sms > /srv/roman-sms/backups/pre_<migration>_YYYY_MM_DD.dump

The pre-department rollback backup from 2026-11-09 is at
`/srv/roman-sms/backups/pre_department_2026_11_09.sql` (508 KB, 28
CREATE TABLE statements, verified 2026-11-09). If the A1 migration ever
needed to be reverted (it won't; the code has shipped), this is the
restore point.

**Restore from schema backup.** Only useful for creating a fresh DB
with the right structure:

    psql -U roman -d roman_sms_new -f /srv/roman-sms/backups/backup_YYYY_MM_DD.sql

Then run `flask db stamp <head>` to tell Alembic the schema is already
at head (the backup has the tables; Alembic needs the version row).

**What is not covered.** Row data, WAL, PITR, off-site replication.
If the droplet's disk fails and Postgres is lost, the data is gone
beyond what the last schema backup captured. **This is a known gap.**
The mitigation currently in place is that production is small enough
(5 orgs, low thousands of rows) that a manual `pg_dump` before any
risky operation is fast and feasible. If the platform grows to the
point where that is not true, off-site `pg_dump` cron must be added.

**Verifying a backup.** Every backup should be run against a fresh
`roman_sms_scratch` DB and `flask db current` should print head. A
backup that can't be restored is not a backup. `flask backup` (CLI)
produces a fresh schema dump; the cron invokes it. See §8.6.

## 8.4 SMTP

**Mailgun on port 2525.** DigitalOcean permanently blocks ports 25,
465, and 587 — this is a platform policy, not a suggestion. Any SMTP
config using the standard ports will time out silently or connect-fail
on this droplet. Mailgun's port 2525 is the working configuration and
must not be changed to a "standard" port.

    MAIL_SERVER=smtp.mailgun.org
    MAIL_PORT=2525
    MAIL_USE_TLS=true
    MAIL_USERNAME=postmaster@mg.romansms.com
    MAIL_PASSWORD=<mailgun SMTP password>

**Domain verification.** `mg.romansms.com` is verified in Mailgun via
TXT and CNAME records on the parent domain. The sending address is
`no-reply@romansms.com` (delivered via Mailgun's `mg.` subdomain).
SPF, DKIM, and DMARC all pass on outbound mail. Do not send from
addresses outside the verified domain — it will fail SPF and likely be
silently dropped.

**What mail is sent:** signup acknowledgement, master signup
notification, welcome / set-password link, user-initiated password
reset, campaign completion, and audit alerts. All via `mailer.py` (see
`08-services.md` §7a.22). No transactional emails go through any other
channel.

**Testing SMTP.** `flask egosms-test` tests the SMS provider, not
email. For email testing, use a script that calls
`mailer.send_welcome(test@example.com, "http://test")` and checks the
destination inbox. There is no CLI command for email-test; a one-line
Python snippet does it. If a production email fails, check Mailgun's
activity log first (the failure is almost always auth or SPF).

## 8.5 Incident response

The general shape of an incident — the details vary, the sequence does
not:

**1. Identify.** What is wrong? `/health` returning non-200, users
reporting failures, worker not sending, or a metric out of range?
**Narrow before acting.** An "outage" is often a single slow query, not
a full-system failure.

**2. Contain.** If the incident involves an abusive account, suspend
the org (`/master/orgs/<id>/edit` → set `active=False`). If it involves
runaway dispatch (rate-limit bypass, unexpected volume), stop the
worker: `sudo systemctl stop roman-worker`. That halts all sending
without touching the web app. Restarting the worker after a fix
resumes the queue from where it stopped — no messages are lost.

**3. Diagnose.** In this order:

    # Current state
    systemctl is-active roman-sms roman-worker roman-panel
    systemctl status roman-worker --no-pager -l

    # Recent errors (worker)
    journalctl -u roman-worker -n 200 --no-pager

    # Recent errors (web)
    journalctl -u roman-sms -n 200 --no-pager

    # Database
    sudo -u postgres psql -d roman_sms -c "SELECT count(*) FROM pg_stat_activity WHERE state != 'idle';"

    # Migration head
    cd /srv/roman-sms && source venv/bin/activate && flask db current

Common failure modes:

- **Worker stuck on a slow Pahappa call.** `journalctl` shows a message
  stuck in `processing`. `SELECT ... FOR UPDATE SKIP LOCKED` on
  `send_queue` means a stuck row does not block others, but a worker
  stuck on a specific job does delay subsequent ones in the same batch.
  Fix: check Pahappa's status, restart worker.
- **Web app 500s under load.** `journalctl -u roman-sms` shows the
  traceback. Gunicorn with 3 workers × 4 threads = 12 concurrent
  requests. If sustained traffic exceeds that, workers queue — visible
  in nginx access logs as long response times, not 500s. 500s are code
  bugs, not overload.
- **Wallet reconciliation mismatch.** `flask reconcile` reports
  drift. **Do not auto-fix.** Investigate the specific transaction
  rows. A real mismatch means a write happened outside the ledger
  (impossible through the service layer, possible through a bug that
  bypassed it) — the cause matters more than the correction.
- **Migration stuck.** `flask db upgrade` hung. Postgres
  `pg_stat_activity` shows the session. Usually a table lock; find the
  blocking session with `pg_blocking_pids()`. Do not `kill -9` the
  migration — that can leave the schema half-applied.

**4. Fix.** Restore from backup if data is lost (§8.3). Roll back the
deploy if the incident began with a deploy (§8.2 rollback). Fix the
code and redeploy if the cause is a bug.

**5. Communicate.** The chat channel (`/chat`) is the associate-facing
communication channel. For platform-wide incidents (SMTP outage,
worker down, prolonged degraded service), post in **broadcast**, not
one DM per org. The broadcast reaches every associate.

**6. Post-incident.** What was the cause? What detection failed? What
would have caught it earlier? If the answer is "nothing would have",
that's a monitoring gap. Log the incident — a `docs/incidents/` file
in the repo is the current mechanism; future automation could write to
the audit log.

## 8.6 CLI verification

The 16 registered CLI commands, per `STRUCTURE.md`. Each is meant to be
safe to run and self-describing. `flask <command> --help` should be the
first line of defense before running anything.

### Seeding

| Command | Purpose | Safe on prod? |
|---|---|---|
| `flask seed-all` | Seed master org, plans, districts, system org — full bootstrap | **NO** — creates orgs and users |
| `flask seed` | Seed within an existing DB (idempotent) | With care — checks existing rows |
| `flask seed-districts` | Populate `district` table | Yes — idempotent |

### Fund management

| Command | Purpose | Safe on prod? |
|---|---|---|
| `flask fund-master <amount>` | Add credits to master wallet from Pahappa | Yes (audited) |
| `flask fund-platform <amount>` | Add credits to system sender wallet | Yes (audited) |
| `flask grant <org_id> <amount>` | Grant credits to a specific org | Yes (audited) |

**`flask fund-*` sources real credits.** The ledger invariant
(`08-services.md` §7a.2) requires every credit to have a source. `fund-*`
commands create `master_topup` or `pahappa_sync` transactions with the
right whitelisted reason. Do not run them speculatively — every run
adds credits that the wallet treats as real.

### Orgs and users

| Command | Purpose | Safe on prod? |
|---|---|---|
| `flask create-org <slug> <name> <email>` | Create an associate org directly | With care — creates live tenant |
| `flask reset-password <email>` | Set a new random password, print it | Yes (audited) |

**`flask reset-password`** is the last-resort admin recovery path.
When a school loses all admins, master uses this (via web panel) or the
CLI. The new password is printed to stdout — capture it, deliver it to
the user via a secure channel (phone call, not chat), and require the
user to change it on first login.

### Send testing

| Command | Purpose | Safe on prod? |
|---|---|---|
| `flask bulk-send <csv> <body>` | Send to a list of phones | **NO** — spends real credits |
| `flask egosms-balance` | Query Pahappa balance | Yes (read-only) |
| `flask egosms-test <phone>` | Send a test SMS to one phone | Yes (1 credit, purposeful) |

### Maintenance

| Command | Purpose | Safe on prod? |
|---|---|---|
| `flask reconcile` | Verify wallet ledger invariant per org | Yes (read-only) |
| `flask expire-subs` | Mark subscriptions past `expires_at` as expired | Yes (idempotent) |
| `flask backup` | Produce a schema dump to `/srv/roman-sms/backups/` | Yes (writes a file) |
| `flask info` | Print version, head, counts, prod state | Yes (read-only) |

### Verification before any risky operation

Before any of the "care" commands, run `flask info`. It prints the
current prod state — head revision, org count, user count, active
subscription count, master wallet balance. Compare against what you
expect. A surprising count means either a legitimate change or a
problem; find out which before proceeding.

## 8.7 The working style that produced this document

Rules learned across the 2026-11-10 → 2026-11-13 arc, then the
documentation arc that followed. These govern how changes are made on
this codebase.

### Inspection before writing

- **Inspect before writing.** Enumerate files before editing a class.
  `inspect.getsource()` proves existence, not file location — a
  function can exist in memory from a stale import.
- **A grep match is a claim that needs context.** Follow with `-Context
  2,2` before deciding to fix. A match on `department` may be a
  variable, a column, or a comment — read the surrounding lines.
- **Test fixture tracing.** Trace mutations to the assertion point,
  not the function entry. A test that passes because it doesn't
  actually exercise the change is worse than no test.

### Paste discipline

- **Single-write-gate for multi-file pastes.** Read all → verify all
  anchors → apply all mutations in memory → verify mutations → write
  all → verify on disk. Any failure before write leaves zero disk
  changes. This is ADR-028.
- **A throw in a pasted line does not stop later lines.** The
  mutation must be the last line of the paste, or inside an `if/else`
  where the else contains the mutation. Otherwise the mutation fires
  even after the guard throws.
- **EOL awareness.** Files may be CRLF or LF. Use `IndexOf` on
  single-line substrings for EOL-agnostic anchors. Position-based
  insertion (`LastIndexOf`) beats multi-line literal replace for
  templates.
- **Phantom file detection.** After any multi-file paste, `git status
  --short`. Any unexpected `??` file is a bug in the paste. Delete and
  investigate — do not commit around it.

### Verification discipline

- **Test first, commit second.** Run tests, paste exit code, then
  commit.
- **A green test is a claim.** It proves the assertion passed, not
  that the feature works. Browser or CLI verification after tests is
  the only proof.
- **Verification vs. feature sessions are different.** Both are
  valuable. Do not skip verification sessions because the feature
  session "already proved it works."
- **Byte-level verification of pasted files.** Every pasted
  Markdown/`.docx` file is followed by `[System.IO.File]::ReadAllBytes`
  + UTF-8 decode + regex count on em-dash / section-sign / expected
  markers. The console lies; the bytes don't. Five clean checks across
  this document's five stages, zero false-positives on the byte-level
  path.

### Windows / PowerShell specifics

- **No triple-backtick fences in PowerShell heredocs.** The ```
  sequence trips the paste handler with `^C` mid-heredoc. Use 4-space
  indented code blocks instead.
- **`-ErrorAction Stop`** on any `Remove-Item` / `Set-Content` whose
  failure matters. Without it, the error is non-terminating and the
  next line runs anyway.
- **`$env:PATH` refresh after pandoc install.** On a fresh PowerShell
  session: `$env:PATH = [Environment]::GetEnvironmentVariable("PATH",
  "Machine") + ";" + [Environment]::GetEnvironmentVariable("PATH",
  "User")`. Without this, `pandoc --version` reports "not recognized"
  even though pandoc is installed at machine level.
- **Word lock files.** A `.docx` open in Word holds a `~$...docx`
  lock. `Stop-Process -Name WINWORD -Force` releases it; the lock file
  then becomes an orphan and can be deleted (it's gitignored via
  `docs/~$*`). Attempting to regenerate a `.docx` while Word has it
  open produces `permission denied` from pandoc and cascading null
  errors in any downstream `System.IO.Compression` calls.

### Documentation project specifics (this arc)

- **Markdown via PowerShell heredoc, 4-space indented code blocks.**
  No triple-backtick fences.
- **Every `WriteAllText` must be preceded by a check that the variable
  is not null/empty.** `Set-Content $null` overwrites with empty
  content. The pattern is `if ([string]::IsNullOrEmpty($x)) { throw
  "..." }; [IO.File]::WriteAllText(..., $x)`.
- **Dedupe pattern.** `IndexOf` (first) → `IndexOf` (second) →
  `Substring(0, second)` truncates cleanly. For appending to a file
  with duplicate sections.
- **Multi-file "independent write blocks" are not a single-write-gate.**
  Each block must be fully self-contained or the whole paste must use
  the single-write-gate pattern.
- **Regenerate `.docx` after each stage** and verify by size and
  content markers. A stale `.docx` that doesn't include the latest
  stage is worse than no `.docx` — it looks current.

## 8.8 Where to look when something is wrong

A short index of common questions:

| Question | Where |
|---|---|
| What SHA is prod on? | `cd /srv/roman-sms && git rev-parse --short HEAD` |
| What migration head? | `flask db current` |
| Is the worker running? | `systemctl is-active roman-worker` |
| Is mail going out? | Mailgun activity log; then `journalctl -u roman-sms -n 200` |
| Is SMS going out? | `flask egosms-balance`; `journalctl -u roman-worker -n 200` |
| What was the last deploy? | `git log -1 --oneline` on prod + `journalctl -u roman-sms --since yesterday \| head -50` |
| Where are backups? | `/srv/roman-sms/backups/` |
| Where is the master console? | `https://romansms.com/master` (master login only) |
| Where is the ops panel? | SSH tunnel to `127.0.0.1:8080` (see §8.1) |
| How do I roll back? | §8.2 "Rollback" |
| What if the worker is stuck? | §8.5 "Diagnose" — restart first, investigate second |

---

*Part 8 of 10. See `10-adrs.md` next.*