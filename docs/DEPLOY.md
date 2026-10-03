# Deployment

Target: a single Ubuntu 22.04 VPS running Postgres, nginx, and two systemd
units. Deploys go through `git pull`, not rsync — the repo lives on GitHub
and the server has a read-only deploy key.

Everything below is written for a fresh server. If you're re-deploying
after code changes, skip to **Subsequent deploys**.

---

## Prerequisites

- Domain pointing at the server (`A` record → server IP)
- Ubuntu 22.04 (or 24.04; paths are identical)
- A GitHub account with the repo created and pushed
- Live Pahappa credentials (contact their support — no self-service signup)
- A decision on SMTP provider for outbound email

The following are installed during server setup, not before:

- Postgres 14 or later
- Python 3.11 or later
- nginx
- git

---

## Server setup

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip postgresql nginx git certbot python3-certbot-nginx

# System user for the app. No shell, no home-dir clutter.
sudo adduser --system --group roman
sudo mkdir -p /opt/roman-sms
sudo chown roman:roman /opt/roman-sms

# Backups directory, owned by the app user.
sudo mkdir -p /var/backups/roman-sms
sudo chown roman:roman /var/backups/roman-sms