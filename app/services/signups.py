"""
Self-signup service.

An applicant submits a SignupRequest. The master approves or rejects.
On approval we create the Organization, its first User, and a starter
credit grant — all in one transaction.
"""
import re
import secrets
from datetime import datetime

from flask import current_app

from app.extensions import db
from app.models import (Organization, User, Plan, SignupRequest,
                        Subscription, District)
from app.services import wallet as wallet_svc
from app.services import mailer
from app.services.audit import log as audit


SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$')

STARTER_CREDITS_DEFAULT = 100


class SignupError(Exception):
    pass


# ----------------------------------------------------------------------
# Public: submit
# ----------------------------------------------------------------------

def submit_request(*, company_name, desired_slug, brand_name,
                   contact_name, contact_email, contact_phone=None,
                   district_id=None, plan_id=None,
                   expected_volume=None, message=None,
                   ip_address=None, user_agent=None):
    """
    Create a pending SignupRequest. Does not touch Organization.

    Validates and normalises, but does not enforce uniqueness on the
    slug — the master may want to override it at approval time. It does
    refuse if the slug or email already belong to a real org/user.
    """
    company_name = (company_name or '').strip()
    brand_name = (brand_name or company_name).strip()
    contact_name = (contact_name or '').strip()
    contact_email = (contact_email or '').strip().lower()
    desired_slug = (desired_slug or '').strip().lower()

    if not company_name:
        raise SignupError('Company name is required.')
    if not contact_name:
        raise SignupError('Your name is required.')
    if not contact_email or '@' not in contact_email:
        raise SignupError('A valid email address is required.')
    if not SLUG_RE.match(desired_slug):
        raise SignupError(
            'URL slug must be 3-50 characters, lowercase letters, '
            'numbers, and dashes.'
        )
    if len(brand_name) > 20:
        raise SignupError('Brand prefix must be 20 characters or fewer.')

    # Slug collision against live orgs
    if Organization.query.filter_by(slug=desired_slug).first():
        raise SignupError(
            f'The slug "{desired_slug}" is already in use. '
            f'Try a variation.'
        )

    # Email collision against live users
    if User.query.filter_by(email=contact_email).first():
        raise SignupError(
            'That email is already registered. '
            'Try signing in instead.'
        )

    # Do not create duplicate pending requests from the same email
    existing = (SignupRequest.query
                .filter_by(contact_email=contact_email, status='pending')
                .first())
    if existing:
        return existing, False

    # Resolve district if provided
    if district_id:
        if not db.session.get(District, district_id):
            district_id = None

    # Resolve plan if provided
    if plan_id:
        if not db.session.get(Plan, plan_id):
            plan_id = None

    req = SignupRequest(
        company_name=company_name,
        desired_slug=desired_slug,
        brand_name=brand_name,
        district_id=district_id,
        contact_name=contact_name,
        contact_email=contact_email,
        contact_phone=(contact_phone or '').strip() or None,
        plan_id=plan_id,
        expected_volume=(expected_volume or '').strip() or None,
        message=(message or '').strip() or None,
        ip_address=(ip_address or '')[:45] or None,
        user_agent=(user_agent or '')[:255] or None,
        status='pending',
    )
    db.session.add(req)
    db.session.commit()

    audit('signup_submitted',
          f'id={req.id} company={company_name!r}',
          actor_id=None)

    _send_acknowledgement(req)
    _notify_master(req)

    return req, True


def _send_acknowledgement(req):
    try:
        mailer.send(
            to=req.contact_email,
            subject='Roman SMS — we received your application',
            body_text=(
                f'Hello {req.contact_name},\n\n'
                f'Thanks for applying for a Roman SMS account for '
                f'{req.company_name}.\n\n'
                f'We review every application manually and reply within '
                f'one working day. If approved, you will receive a '
                f'second email with a link to set your password.\n\n'
                f'If you did not submit this request, please reply to '
                f'this email so we can investigate.\n\n'
                f'— Roman SMS'
            ),
        )
    except Exception as e:
        current_app.logger.error('Signup ack email failed: %s', e)


def _notify_master(req):
    """Send an email to ALERT_EMAIL. In-app notification is computed."""
    alert_to = current_app.config.get('ALERT_EMAIL')
    if not alert_to:
        return
    try:
        mailer.send(
            to=alert_to,
            subject=f'New signup: {req.company_name}',
            body_text=(
                f'Company:  {req.company_name}\n'
                f'Contact:  {req.contact_name} <{req.contact_email}>\n'
                f'Phone:    {req.contact_phone or "-"}\n'
                f'Slug:     {req.desired_slug}\n'
                f'Brand:    {req.brand_name}\n'
                f'Volume:   {req.expected_volume or "-"}\n\n'
                f'Message:\n{req.message or "(none)"}\n\n'
                f'Review: /master/signups'
            ),
        )
    except Exception as e:
        current_app.logger.error('Signup master notification failed: %s', e)


# ----------------------------------------------------------------------
# Master: read
# ----------------------------------------------------------------------

def list_requests(*, status=None, limit=200):
    q = SignupRequest.query
    if status:
        q = q.filter_by(status=status)
    return (q.order_by(SignupRequest.created_at.desc())
            .limit(limit).all())


def get(request_id):
    return db.session.get(SignupRequest, request_id)


def pending_count():
    return SignupRequest.query.filter_by(status='pending').count()


# ----------------------------------------------------------------------
# Master: approve / reject
# ----------------------------------------------------------------------

def approve(req, *, actor, starter_credits=None):
    """
    Create the Organization, its first User, and a starter credit grant
    in one transaction.

    Starter credits come from SIGNUP_STARTER_CREDITS config unless
    explicitly passed.

    Returns (org, user, starter_credits_granted).
    """
    if req.status != 'pending':
        raise SignupError(f'Request is already {req.status}.')

    # Re-validate slug and email — they may have been taken since submit.
    if Organization.query.filter_by(slug=req.desired_slug).first():
        raise SignupError(
            f'Slug "{req.desired_slug}" is now taken. '
            f'Edit the request before approving.'
        )
    if User.query.filter_by(email=req.contact_email).first():
        raise SignupError(
            'That email is now registered. '
            'Edit the request before approving.'
        )

    master = Organization.query.filter_by(is_master=True).first()
    if not master:
        raise SignupError('Master org missing. Run seed.')

    # Create org
    org = Organization(
        name=req.company_name,
        slug=req.desired_slug,
        brand_name=req.brand_name,
        status='active',
        is_master=False,
        is_system=False,
        parent_id=master.id,
        contact_email=req.contact_email,
        contact_phone=req.contact_phone,
        district_id=req.district_id,
    )
    db.session.add(org)
    db.session.flush()

    # Create admin user with a random password. The real password is set
    # by the applicant via the welcome email link.
    user = User(
        email=req.contact_email,
        full_name=req.contact_name,
        role='associate_admin',
        org_id=org.id,
    )
    user.set_password(secrets.token_urlsafe(32))
    db.session.add(user)
    db.session.flush()

    # Starter credit grant
    if starter_credits is None:
        starter_credits = current_app.config.get(
            'SIGNUP_STARTER_CREDITS', STARTER_CREDITS_DEFAULT)
    starter_credits = int(starter_credits or 0)

    if starter_credits > 0:
        wallet_svc.credit(
            org.id, starter_credits,
            reason='plan_grant',
            reference=f'signup:{req.id}',
            note='Welcome credits',
            actor_id=actor.id,
        )

    req.status = 'approved'
    req.reviewed_by = actor.id
    req.reviewed_at = datetime.utcnow()
    req.created_org_id = org.id
    req.created_user_id = user.id

    db.session.commit()

    audit('signup_approved',
          f'id={req.id} org={org.slug} credits={starter_credits}',
          org_id=org.id, actor_id=actor.id)

    _send_welcome(org, user)

    return org, user, starter_credits


def reject(req, *, actor, reason):
    if req.status != 'pending':
        raise SignupError(f'Request is already {req.status}.')

    reason = (reason or '').strip()
    if not reason:
        raise SignupError('A reason is required.')

    req.status = 'rejected'
    req.reviewed_by = actor.id
    req.reviewed_at = datetime.utcnow()
    req.rejection_reason = reason[:255]
    db.session.commit()

    audit('signup_rejected',
          f'id={req.id} reason={reason[:100]}',
          actor_id=actor.id)

    _send_rejection(req)


def mark_spam(req, *, actor):
    if req.status != 'pending':
        raise SignupError(f'Request is already {req.status}.')
    req.status = 'spam'
    req.reviewed_by = actor.id
    req.reviewed_at = datetime.utcnow()
    db.session.commit()
    audit('signup_spam', f'id={req.id}', actor_id=actor.id)


# ----------------------------------------------------------------------
# Welcome / rejection emails
# ----------------------------------------------------------------------

def _send_welcome(org, user):
    from app.services import password_reset

    token = password_reset.make_token(user, purpose='welcome')
    base = current_app.config.get('PUBLIC_BASE_URL', '')
    url = (f'{base.rstrip("/")}/reset-password/{token}'
           if base else f'/reset-password/{token}')

    try:
        mailer.send(
            to=user.email,
            subject=f'Welcome to Roman SMS — set your password',
            body_text=(
                f'Hello {user.full_name},\n\n'
                f'Your Roman SMS account for {org.name} is ready.\n\n'
                f'Set your password using this link:\n{url}\n\n'
                f'The link expires in 24 hours.\n\n'
                f'Once you have set a password, you can sign in at:\n'
                f'{base or ""}/login\n\n'
                f'Your brand prefix on every outgoing SMS will be: '
                f'"{org.brand_name}: "\n\n'
                f'We have added a small welcome credit grant to your '
                f'wallet so you can send a test campaign.\n\n'
                f'— Roman SMS'
            ),
        )
    except Exception as e:
        current_app.logger.error('Welcome email failed: %s', e)


def _send_rejection(req):
    try:
        mailer.send(
            to=req.contact_email,
            subject='Roman SMS — application update',
            body_text=(
                f'Hello {req.contact_name},\n\n'
                f'Thank you for applying for a Roman SMS account.\n\n'
                f'We are not able to approve your application at this '
                f'time.\n\n'
                f'Reason: {req.rejection_reason}\n\n'
                f'You are welcome to reply to this email if you think '
                f'this is an error.\n\n'
                f'— Roman SMS'
            ),
        )
    except Exception as e:
        current_app.logger.error('Rejection email failed: %s', e)