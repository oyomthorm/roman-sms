from datetime import datetime
from app.extensions import db
from app.models import Contact, Campaign, MessageLog, SendQueue, OptOut
from app.services import wallet as wallet_svc
from app.services.entitlements import check_can_send, EntitlementError
from app.services.renderer import render, segments
from app.services.audit import log as audit
from collections import namedtuple

Recipient = namedtuple('Recipient', ['id', 'phone', 'name'])

class CampaignError(Exception):
    pass


def preview(org, body, group_id=None, district_id=None, limit=5):
    contacts = resolve_recipients(org.id, group_id, district_id)[:limit]
    return [{'contact': c, 'body': render(org, body, c)}
            for c in contacts]


def estimate(org, body, group_id=None, district_id=None):
    """Return (recipient_count, total_segments)."""
    contacts = resolve_recipients(org.id, group_id, district_id)
    total = sum(segments(render(org, body, c)) for c in contacts)
    return len(contacts), total

from collections import namedtuple




def resolve_recipients(org_id, group_id=None, district_id=None,
                       custom_phones=None):
    """
    Return a list of recipient-like objects, each with .id, .phone, .name.

    - custom_phones: if given, use those numbers (already normalised),
      skipping opt-outs and enriching any that match a known contact.
    - otherwise: org-scoped contacts, not opted out, filtered by
      group/district, minus the platform-wide opt-out list.
    """
    blocked = {r[0] for r in db.session.query(OptOut.phone).all()}

    if custom_phones:
        valid = [p for p in custom_phones if p not in blocked]
        if not valid:
            return []
        known = {
            c.phone: c
            for c in Contact.query.filter(
                Contact.org_id == org_id,
                Contact.phone.in_(valid)
            ).all()
        }
        out = []
        for phone in valid:
            c = known.get(phone)
            if c:
                out.append(c)
            else:
                out.append(Recipient(id=None, phone=phone, name=None))
        return out

    q = Contact.query.filter_by(org_id=org_id, opted_out=False)
    if group_id:
        q = q.filter_by(group_id=group_id)
    if district_id:
        q = q.filter_by(district_id=district_id)
    contacts = q.all()
    return [c for c in contacts if c.phone not in blocked]


def create_campaign(org, *, name, body,
                    group_id=None, group_name=None,
                    district_id=None, district_name=None,
                    custom_phones=None,
                    template_id=None, created_by=None,
                    scheduled_at=None):
    """
    The whole send pipeline, minus the actual network call.

    custom_phones: optional list of already-normalised phone strings.
      When given, group_id/district_id are ignored, and only those
      numbers are messaged. Used by the "Paste numbers" recipient
      source on the campaign form.

    Returns (campaign, total_segments).
    Raises CampaignError on any rule violation.
    """
    name = (name or '').strip()
    body = (body or '').strip()
    if not name or not body:
        raise CampaignError('Campaign name and message body are required.')

    contacts = resolve_recipients(
        org.id, group_id, district_id, custom_phones=custom_phones)
    if not contacts:
        raise CampaignError(
            'No eligible recipients for this selection.'
            if not custom_phones
            else 'No valid recipients in the pasted list.'
        )

    rendered = [(c, render(org, body, c)) for c in contacts]
    total_segments = sum(segments(msg) for _, msg in rendered)

    try:
        check_can_send(org, total_segments)
    except EntitlementError as e:
        raise CampaignError(str(e))

    # Name the campaign so pasted-number sends are distinguishable.
    if custom_phones and not group_name:
        group_name = f'Pasted ({len(contacts)})'

    campaign = Campaign(
        org_id=org.id, name=name, body=body,
        template_id=template_id, sender_id=org.brand_name,
        group_filter=group_name, district_filter=district_name,
        status='queued',
        total=len(contacts), created_by=created_by,
        scheduled_at=scheduled_at,
    )
    db.session.add(campaign)
    db.session.flush()

    try:
        wallet_svc.debit(
            org.id, total_segments, reason='sms_send',
            reference=f'campaign:{campaign.id}',
            note=f'{len(contacts)} recipients, {total_segments} segments',
            actor_id=created_by,
        )
        campaign.credits_debited = total_segments
    except wallet_svc.InsufficientCredits as e:
        db.session.rollback()
        raise CampaignError(str(e))

    for contact, msg in rendered:
        db.session.add(MessageLog(
            org_id=org.id, campaign_id=campaign.id,
            contact_id=contact.id,
            phone=contact.phone,
            body=msg, status='pending',
        ))

    db.session.add(SendQueue(
        campaign_id=campaign.id, org_id=org.id,
        status='pending', run_after=scheduled_at or datetime.utcnow(),
    ))

    db.session.commit()
    audit('campaign_queued',
          f'id={campaign.id} recipients={len(contacts)} '
          f'segments={total_segments}')
    return campaign, total_segments


def cancel_campaign(campaign, *, actor_id=None):
    """Idempotent. Cancels pending messages and pending queue rows."""
    if campaign.status in ('complete', 'cancelled'):
        return False
    campaign.status = 'cancelled'
    (MessageLog.query
     .filter_by(campaign_id=campaign.id, status='pending')
     .update({'status': 'cancelled'}, synchronize_session=False))
    (SendQueue.query
     .filter_by(campaign_id=campaign.id, status='pending')
     .update({'status': 'failed', 'last_error': 'cancelled'},
             synchronize_session=False))
    db.session.commit()
    audit('campaign_cancel', f'id={campaign.id}', actor_id=actor_id)
    return True


def delivery_breakdown(campaign_id):
    """
    Return a dict {status: count} for a campaign's messages.
    Includes 'delivered' and 'delivery_failed' once the webhook
    reports them.
    """
    rows = (db.session.query(MessageLog.status,
                             db.func.count(MessageLog.id))
            .filter_by(campaign_id=campaign_id)
            .group_by(MessageLog.status)
            .all())
    return {status: count for status, count in rows}