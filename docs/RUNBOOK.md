# Runbook

Day-to-day operations and incident response. Read this when something
breaks, or once a month as a refresher.

## Daily checks

```bash
systemctl status roman-sms roman-worker
journalctl -u roman-worker -n 50 --no-pager