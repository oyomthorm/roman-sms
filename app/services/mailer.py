"""
Pluggable mailer. Backend is chosen by MAIL_BACKEND config:

  console — writes emails to the log (dev default)
  smtp    — sends through an SMTP server

Never raises on delivery failure. All failures are logged.
"""
import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

log = logging.getLogger('roman.mailer')


def send(to, subject, body_text, body_html=None):
    backend = current_app.config.get('MAIL_BACKEND', 'console')
    if backend == 'console':
        log.info('=== MAIL (console) ===\nTo: %s\nSubject: %s\n\n%s\n=== END ===',
                 to, subject, body_text)
        return True
    if backend == 'smtp':
        return _send_smtp(to, subject, body_text, body_html)
    log.error('Unknown MAIL_BACKEND: %s', backend)
    return False


def _send_smtp(to, subject, body_text, body_html):
    cfg = current_app.config
    msg = EmailMessage()
    msg['From'] = cfg.get('MAIL_FROM', 'no-reply@romansms.local')
    msg['To'] = to
    msg['Subject'] = subject
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype='html')

    try:
        with smtplib.SMTP(cfg['MAIL_HOST'], cfg.get('MAIL_PORT', 587),
                          timeout=15) as s:
            if cfg.get('MAIL_USE_TLS', True):
                s.starttls()
            if cfg.get('MAIL_USERNAME'):
                s.login(cfg['MAIL_USERNAME'], cfg['MAIL_PASSWORD'])
            s.send_message(msg)
        return True
    except Exception as e:
        log.exception('SMTP send failed: %s', e)
        return False