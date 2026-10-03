"""
Invoice service. The single source of truth for turning money into credits.

Design rules:
  - All amounts, credits, and validity are SNAPSHOTTED on the invoice at
    creation. Later edits to the plan do not affect invoices already issued.
  - mark_paid is atomic: invoice update, subscription creation, and wallet
    credit all commit or none of them do.
  - Cancelling an invoice is terminal. A new invoice must be created to retry.
"""
import secrets
from datetime import datetime, timedelta

from app.extensions import db
from app.models import Invoice, Plan, Subscription
from app.services import wallet as wallet_svc
from app.services.audit import log as audit


class BillingError(Exception):
    pass


ALLOWED_PAYMENT_METHODS = {'momo', 'bank', 'cash', 'other'}


# --------------------------------------------------------------------------
# Numbering
# --------------------------------------------------------------------------

def _new_number():
    """
    Invoice numbers look like INV-20261008-A3F29B.
    Human-readable, sortable by date, collision-safe enough for this scale.
    If sequential numbering becomes a requirement, replace this with a
    Sequence table.
    """
    stamp = datetime.utcnow().strftime('%Y%m%d')
    token = secrets.token_hex(3).upper()
    return f'INV-{stamp}-{token}'


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------

def list_for_org(org, limit=50):
    return (Invoice.query
            .filter_by(org_id=org.id)
            .order_by(Invoice.id.desc())
            .limit(limit)
            .all())


def list_all(*, status=None, org_id=None, limit=200):
    q = Invoice.query
    if status:
        q = q.filter_by(status=status)
    if org_id:
        q = q.filter_by(org_id=org_id)
    return q.order_by(Invoice.id.desc()).limit(limit).all()


def get_for_org(org, invoice_id):
    return Invoice.query.filter_by(id=invoice_id, org_id=org.id).first()


def get_any(invoice_id):
    return db.session.get(Invoice, invoice_id)


def unpaid_for_org(org):
    return (Invoice.query
            .filter_by(org_id=org.id, status='unpaid')
            .order_by(Invoice.id.desc())
            .all())


# --------------------------------------------------------------------------
# Create
# --------------------------------------------------------------------------

def create_invoice(org, plan, *, actor_id=None, note=None):
    """
    Create an unpaid invoice for org buying plan.
    Reuses an existing unpaid invoice for the same plan rather than
    creating duplicates from double-clicks.
    """
    if not plan or not plan.is_active:
        raise BillingError('That plan is not available.')

    existing = (Invoice.query
                .filter_by(org_id=org.id, plan_id=plan.id, status='unpaid')
                .first())
    if existing:
        return existing, False

    invoice = Invoice(
        org_id=org.id,
        plan_id=plan.id,
        plan_name=plan.name,
        number=_new_number(),
        status='unpaid',
        amount=plan.price,
        currency=plan.currency,
        credits=plan.credits,
        validity_days=plan.validity_days,
        note=(note or '').strip() or None,
    )
    db.session.add(invoice)
    db.session.commit()

    audit('invoice_create',
          f'number={invoice.number} plan={plan.name} amount={plan.price}',
          org_id=org.id, actor_id=actor_id)
    return invoice, True


# --------------------------------------------------------------------------
# Mark paid — the important one
# --------------------------------------------------------------------------

def mark_paid(invoice, *, actor_id,
              payment_method, payment_reference,
              duration_days=None, note=None):
    """
    Turn an unpaid invoice into credits and a subscription.

    Atomic:
      1. Expire any existing active subscription for the org.
      2. Create a new Subscription from the invoice snapshot.
      3. Credit the wallet with the invoice's credits.
      4. Mark the invoice paid.

    All four commit together.
    """
    if invoice.status != 'unpaid':
        raise BillingError(f'Invoice is {invoice.status}, not unpaid.')

    method = (payment_method or '').strip().lower()
    if method not in ALLOWED_PAYMENT_METHODS:
        raise BillingError(
            f'Payment method must be one of: '
            f'{", ".join(sorted(ALLOWED_PAYMENT_METHODS))}.'
        )

    reference = (payment_reference or '').strip()
    if not reference:
        raise BillingError('Payment reference is required.')

    org = invoice.org
    duration = int(duration_days or invoice.validity_days)
    if duration <= 0:
        raise BillingError('Duration must be positive.')

    now = datetime.utcnow()

    # 1. Expire current active subscriptions.
    (Subscription.query
     .filter_by(org_id=org.id, status='active')
     .update({'status': 'expired'}, synchronize_session=False))

    # 2. New subscription from the snapshot.
    sub = Subscription(
        org_id=org.id,
        plan_id=invoice.plan_id,
        starts_at=now,
        expires_at=now + timedelta(days=duration),
        status='active',
        credits_granted=invoice.credits,
    )
    db.session.add(sub)
    db.session.flush()

    # 3. Credit the wallet with the invoice's snapshot credits.
    if invoice.credits > 0:
        wallet_svc.credit(
            org.id, invoice.credits,
            reason='plan_grant',
            reference=f'invoice:{invoice.number}',
            note=note or f'{invoice.plan_name} ({method} {reference})',
            actor_id=actor_id,
        )

    # 4. Mark invoice paid.
    invoice.status = 'paid'
    invoice.paid_at = now
    invoice.payment_method = method
    invoice.payment_reference = reference
    invoice.marked_paid_by = actor_id

    db.session.commit()

    audit('invoice_paid',
          f'number={invoice.number} amount={invoice.amount} '
          f'method={method} ref={reference} credits={invoice.credits}',
          org_id=org.id, actor_id=actor_id)
    return invoice, sub


# --------------------------------------------------------------------------
# Cancel
# --------------------------------------------------------------------------

def cancel_invoice(invoice, *, actor_id, reason):
    if invoice.status != 'unpaid':
        raise BillingError(f'Only unpaid invoices can be cancelled.')
    reason = (reason or '').strip()
    if not reason:
        raise BillingError('A reason is required.')

    invoice.status = 'cancelled'
    invoice.cancelled_at = datetime.utcnow()
    invoice.cancelled_by = actor_id
    invoice.cancellation_reason = reason
    db.session.commit()

    audit('invoice_cancel', f'number={invoice.number} reason={reason}',
          org_id=invoice.org_id, actor_id=actor_id)
    return invoice