# Runbook

Day-to-day operations and incident response. Read this when something
breaks, or once a month as a refresher.

Production runs on a single DigitalOcean VPS (165.245.199.37, Ubuntu
24.04, Postgres 16). App at /srv/roman-sms/, user oyomthorm. Three
systemd units: roman-sms, roman-worker, roman-panel. Nginx +
Let's Encrypt SSL on https://romansms.com.

## Daily checks

Run these on the VPS:

    systemctl status roman-sms roman-worker roman-panel
    journalctl -u roman-worker -n 50 --no-pager
    journalctl -u roman-sms -n 50 --no-pager
    df -h /

## Deploy sequence (code-only, no migration)

From the local Windows machine:

    cd D:\Dev_Apps\roman_sms
    git fetch origin wip/mobile-api
    git rev-parse --short HEAD
    git rev-parse --short origin/wip/mobile-api    (must match)
    git status --short                              (must be empty)
    python -m pytest tests/ -q                      (must exit 0)
    git push origin wip/mobile-api
    ssh oyomthorm@165.245.199.37 "cd /srv/roman-sms && git pull origin wip/mobile-api && git rev-parse --short HEAD"
    ssh -t oyomthorm@165.245.199.37 "sudo systemctl restart roman-sms roman-worker roman-panel && systemctl is-active roman-sms roman-worker roman-panel"
    curl.exe -sS -o NUL -w "GET / -> %{http_code}\n" https://romansms.com/
    curl.exe -sS -o NUL -w "GET /login -> %{http_code}\n" https://romansms.com/login

## Deploy sequence (with migration)

Insert flask db upgrade between pull and restart:

    ssh oyomthorm@165.245.199.37 "cd /srv/roman-sms && source venv/bin/activate && flask db upgrade && flask db current"
    ssh -t oyomthorm@165.245.199.37 "sudo systemctl restart roman-sms roman-worker roman-panel"

Before any migration: verify /srv/roman-sms/backups/ has a fresh dump.
For destructive migrations (drop column, add NOT NULL to populated
table):

    sudo -u postgres pg_dump roman_sms > /srv/roman-sms/backups/pre_migration_YYYYMMDD_HHMM.sql
    sudo chown oyomthorm:oyomthorm /srv/roman-sms/backups/pre_migration_*.sql

After upgrade: flask db current must print the new-hash followed by (head).

## SSH key auth

Passwordless for oyomthorm. sudo still prompts - always wrap in ssh -t.

Verify: ssh -o BatchMode=yes oyomthorm@165.245.199.37 "echo ok"
returns "ok" without a password prompt if working.

## SMTP configuration

DigitalOcean blocks outbound SMTP on ports 25, 465, 587 - permanent
platform policy. Mailgun on 2525 works.

.env on prod:

    MAIL_BACKEND=smtp
    MAIL_HOST=smtp.mailgun.org
    MAIL_PORT=2525
    MAIL_USE_TLS=1
    MAIL_USERNAME=postmaster@mg.romansms.com
    MAIL_PASSWORD=<Mailgun SMTP password>
    MAIL_FROM=no-reply@mg.romansms.com
    ALERT_EMAIL=oyomthorm.21@gmail.com

If email stops delivering:

1. journalctl -u roman-sms | grep -i mail
2. Test SMTP with a Python one-off (see Testing section)
3. Check Mailgun dashboard for pauses or suppressions
4. Verify DNS TXT records for mg.romansms.com have not changed

## Database backups

Daily cron at 03:00 UTC, schema only. Ad-hoc full dump requires sudo -u postgres:

    sudo -u postgres pg_dump roman_sms > /srv/roman-sms/backups/full_YYYYMMDD.sql
    sudo chown oyomthorm:oyomthorm /srv/roman-sms/backups/full_*.sql

Restore:

    sudo -u postgres psql roman_sms < /srv/roman-sms/backups/full_YYYYMMDD.sql

Pre-department rollback: /srv/roman-sms/backups/pre_department_2026_11_09.sql
(508 KB, 28 tables). Preserve.

## Testing

Full test suite runs locally against Postgres:

    python -m pytest tests/ -q

addopts = -q in pytest.ini combined with CLI -q produces -qq, which
suppresses the summary line. Use $LASTEXITCODE as the authoritative
signal, not the dot count.

Fixtures:
- db - for any test needing app context
- master_org - for create_associate
- subscribed_associate - for check_can_send

Trace mutations to the assertion point, not the function entry.

## CLI verification of user-facing flows

For browser flows (login, form submit, campaign send): use a real
browser. Invoke-WebRequest cannot authenticate through this app's
CSRF+Referer stack.

For state-transition verification (e.g. does edit refund correctly),
use a python one-off against prod via SSH:

    $py = @'
    from app import create_app
    from app.extensions import db
    ... setup, call service, assert state, print
    c.pop()
    '@
    $py | ssh oyomthorm@165.245.199.37 "cat > /srv/roman-sms/tmp_verify.py"
    ssh oyomthorm@165.245.199.37 "cd /srv/roman-sms && source venv/bin/activate && python tmp_verify.py; rm -f tmp_verify.py"

Clean up test data via the FK-aware delete pattern. See
services/orgs.py::_delete_user_fk_aware and prior session cleanup scripts.

## Incident response

Services down:

1. systemctl status roman-sms roman-worker roman-panel
2. journalctl -u roman-sms -n 100 --no-pager
3. journalctl -u roman-worker -n 100 --no-pager
4. sudo systemctl restart roman-sms roman-worker roman-panel
5. If restart fails, run the app directly from the venv to see the traceback

Worker not sending:

1. journalctl -u roman-worker -n 100 --no-pager | grep -i error
2. Check Pahappa (EGOSMS) credentials in .env
3. Check stuck jobs in send_queue

Disk full:

1. df -h /
2. du -sh /srv/roman-sms/backups/*
3. sudo journalctl --vacuum-size=200M

Database connection refused:

1. systemctl status postgresql
2. sudo -u postgres psql -c "SELECT 1"
3. Check /var/log/postgresql/postgresql-16-main.log
4. sudo systemctl restart postgresql

## Logging

Text (dev) or JSON (prod) via app/logging_config.py. Per-request IDs
via X-Request-ID. journalctl -u roman-sms shows application logs.

## Useful one-liners

    systemctl is-active roman-sms roman-worker roman-panel

    sudo -u postgres psql roman_sms -c "SELECT id, delta, reason, balance_after, created_at FROM wallet_transaction WHERE org_id=4 ORDER BY id DESC LIMIT 5;"

    sudo -u postgres psql roman_sms -c "SELECT status, COUNT(*) FROM send_queue GROUP BY status;"

    sudo -u postgres psql roman_sms -c "SELECT id, action, detail, created_at FROM audit_log ORDER BY id DESC LIMIT 20;"