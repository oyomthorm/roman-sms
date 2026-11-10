# Deployment

Target: a single Ubuntu 24.04 VPS running Postgres, nginx, and three
systemd units. Deploys go through git pull against a read-only deploy
key on the server. No rsync, no manual file copy.

This doc assumes the server is already provisioned. For a from-scratch
setup, see the notes at the bottom.

## Current production server

- Host: 165.245.199.37 (DigitalOcean droplet ubuntu-s5-2vcpu-4gb-30gb-mkc1)
- OS: Ubuntu 24.04
- App user: oyomthorm
- App directory: /srv/roman-sms/
- Python: 3.12 venv at /srv/roman-sms/venv/
- Database: Postgres 16, db roman_sms, user roman
- Systemd units:
  - roman-sms.service - gunicorn (3 workers, 127.0.0.1:8000)
  - roman-worker.service - scheduler + send queue drain
  - roman-panel.service - Flask panel on 127.0.0.1:8080
- Nginx + Let's Encrypt SSL on https://romansms.com
- SSH: key auth for oyomthorm works passwordless. sudo still prompts -
  use ssh -t for a TTY.

## Prerequisites

- Domain pointing at the server (A record)
- GitHub repo access (deploy key configured)
- Live Pahappa (EGOSMS) credentials
- Mailgun account with a verified sending domain

## Subsequent deploys (code-only)

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

## Subsequent deploys (with migration)

Same sequence, but insert flask db upgrade between pull and restart:

    ssh oyomthorm@165.245.199.37 "cd /srv/roman-sms && source venv/bin/activate && flask db upgrade && flask db current"
    ssh -t oyomthorm@165.245.199.37 "sudo systemctl restart roman-sms roman-worker roman-panel && systemctl is-active roman-sms roman-worker roman-panel"

Critical checks:
- flask db current must match the migration revision hash after upgrade.
  If not, the migration failed silently.
- Services must show active (three times). If any is failed, check
  journalctl -u <unit> before proceeding.
- Migrations that drop a column or add NOT NULL to a populated table
  need a backup first. See RUNBOOK.md "Database backups".

## Rollback

If a deploy breaks production:

1. Revert the last commit locally (git revert or git reset --hard)
2. Push the revert
3. Pull on VPS
4. If a migration was applied, downgrade it FIRST:
   ssh oyomthorm@165.245.199.37 "cd /srv/roman-sms && source venv/bin/activate && flask db downgrade"
5. Restart the three services

If the migration dropped a column, the data is gone unless the
pre-migration backup is restored. Always take a full dump before a
destructive migration.

## Environment variables

.env at /srv/roman-sms/.env. Key variables:

    SECRET_KEY=<random>
    DATABASE_URL=postgresql+psycopg://roman:<password>@127.0.0.1:5432/roman_sms
    PUBLIC_BASE_URL=https://romansms.com
    SCHEDULER_TZ_OFFSET_HOURS=3
    EGOSMS_*=<Pahappa credentials>
    MAIL_*=<Mailgun SMTP credentials on port 2525>
    ALERT_EMAIL=<master notification address>

DigitalOcean blocks outbound SMTP on 25/465/587. Mailgun on 2525
works. See RUNBOOK.md "SMTP configuration".

## Systemd units

Three units, all under /etc/systemd/system/. Template:

    [Unit]
    Description=Roman SMS <component>
    After=network.target postgresql.service

    [Service]
    Type=simple
    User=oyomthorm
    Group=oyomthorm
    WorkingDirectory=/srv/roman-sms
    Environment="PATH=/srv/roman-sms/venv/bin"
    ExecStart=/srv/roman-sms/venv/bin/<command>
    Restart=always
    RestartSec=5

    [Install]
    WantedBy=multi-user.target

Replace <command> with gunicorn -w 3 -b 127.0.0.1:8000 wsgi:app for
roman-sms, python worker.py for roman-worker, flask run --port 8080
(or gunicorn) for roman-panel.

Enable and start:

    sudo systemctl daemon-reload
    sudo systemctl enable roman-sms roman-worker roman-panel
    sudo systemctl start roman-sms roman-worker roman-panel

## Nginx

Site config at /etc/nginx/sites-available/romansms (symlinked to
sites-enabled). Reverse-proxies / to 127.0.0.1:8000, with SSL
terminated at nginx.

SSL via Let's Encrypt:

    sudo certbot --nginx -d romansms.com -d www.romansms.com

Certificate auto-renews every 90 days via the systemd timer.

## Backups

Daily cron at 03:00 UTC. Schema-only dump to /srv/roman-sms/backups/.
Ad-hoc full dumps need sudo -u postgres. See RUNBOOK.md "Database
backups" for exact commands.

## Fresh server setup (historical reference)

The original setup used a different layout (/opt/roman-sms, user
roman). The current server was migrated to /srv/roman-sms, user
oyomthorm. For a new server today, roughly:

    sudo apt update && sudo apt upgrade -y
    sudo apt install -y python3-venv python3-pip postgresql nginx git certbot python3-certbot-nginx
    sudo adduser oyomthorm
    sudo mkdir -p /srv/roman-sms
    sudo chown oyomthorm:oyomthorm /srv/roman-sms
    sudo mkdir -p /srv/roman-sms/backups
    sudo chown oyomthorm:oyomthorm /srv/roman-sms/backups
    sudo -u oyomthorm bash -c "cd /srv && git clone git@github.com:oyomthorm/roman-sms.git"
    sudo -u oyomthorm bash -c "cd /srv/roman-sms && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    sudo -u postgres createuser -s roman
    sudo -u postgres createdb -O roman roman_sms
    (edit .env with real secrets)
    sudo -u oyomthorm bash -c "cd /srv/roman-sms && source venv/bin/activate && flask db upgrade"

Then add the three systemd units above, enable + start, configure
nginx, run certbot.

## Useful commands

    sudo systemctl show roman-sms --property=ExecStart
    sudo systemctl status roman-sms
    journalctl -u roman-worker -f
    journalctl -u roman-sms -f
    sudo systemctl restart roman-sms
    cd /srv/roman-sms && source venv/bin/activate && flask db current

## What is NOT in this doc

- Pahappa (EGOSMS) account setup - contact their support
- Mailgun account creation - sign up at mailgun.com, verify domain
- Let's Encrypt account setup - certbot handles it automatically
- DNS configuration - registrar-specific

See EGOSMS_NOTES.md for Pahappa quirks. See RUNBOOK.md for operational
procedures.