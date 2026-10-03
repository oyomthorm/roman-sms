"""
Campaign notification emails.

Currently: one email to the campaign creator plus all associate_admins
in the org, sent when a campaign finishes sending.

Called from dispatch.process_job after campaign.status flips to 'complete'.
Never raises — a mail failure must not break the dispatch loop.

Renders the email body with Jinja2's Template directly rather than
Flask's render_template_string — the latter pulls in Flask's context
processors, which expect a request context that the worker does not have.
"""
import logging

from flask import current_app
from jinja2 import Template

from app.extensions import db
from app.models import Campaign, Organization, User
from app.services import mailer


log = logging.getLogger('roman.campaign_notifications')


# Whitespace trimmed with `-` on the control tags so the `{% if %}` block
# does not leave blank lines behind when failed_count is zero.
BODY_TEMPLATE = """\
Your campaign "{{ campaign.name }}" has finished sending.

Recipients: {{ campaign.total }}
Sent:       {{ campaign.sent_count }}
Failed:     {{ campaign.failed_count }}
{%- if campaign.failed_count %}

Failed sends were refunded to your wallet automatically.
{%- endif %}

View the full report: {{ base_url }}/campaigns/{{ campaign.id }}

— Roman SMS
"""


def send_completion_email(campaign_id):
    """
    Send a completion email for a finished campaign.

    Returns the number of emails successfully sent (0 if disabled,
    campaign not found, not complete, or no recipients).

    Never raises.
    """
    try:
        if not current_app.config.get('EMAIL_ON_CAMPAIGN_COMPLETE', True):
            return 0

        campaign = db.session.get(Campaign, campaign_id)
        if not campaign or campaign.status != 'complete':
            return 0

        org = db.session.get(Organization, campaign.org_id)
        if not org:
            return 0

        recipients = _recipients(campaign, org)
        if not recipients:
            log.info('campaign %s complete but no recipients', campaign.id)
            return 0

        base_url = current_app.config.get('PUBLIC_BASE_URL', '').rstrip('/')
        body = Template(BODY_TEMPLATE).render(
            campaign=campaign, base_url=base_url)
        subject = f'Campaign "{campaign.name}" finished'

        sent = 0
        for email in recipients:
            if mailer.send(to=email, subject=subject, body_text=body):
                sent += 1

        log.info('campaign %s completion email sent to %d recipient(s)',
                 campaign.id, sent)
        return sent

    except Exception:
        log.exception('completion email failed for campaign %s', campaign_id)
        return 0


def _recipients(campaign, org):
    """Set of email addresses: creator (if active) + org admins."""
    emails = set()

    if campaign.created_by:
        creator = db.session.get(User, campaign.created_by)
        if creator and creator.email and creator.is_active_flag:
            emails.add(creator.email)

    admins = (User.query
              .filter_by(org_id=org.id, role='associate_admin',
                         is_active_flag=True)
              .all())
    for a in admins:
        if a.email:
            emails.add(a.email)

    return emails