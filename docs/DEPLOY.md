# Deployment

Target: single Ubuntu 22.04 VPS. Postgres, nginx, two systemd units.

## Prerequisites

- Domain pointing at the server
- Postgres 14 or later
- Python 3.11 or later
- nginx

## Server setup

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip postgresql nginx git
sudo adduser --system --group roman
sudo mkdir -p /opt/roman-sms && sudo chown roman:roman /opt/roman-sms