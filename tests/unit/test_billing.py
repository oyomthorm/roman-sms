import pytest
from datetime import datetime, timedelta
from app.models import Invoice, Subscription
from app.services import billing as svc
from app.services import wallet as wallet_svc


def test_create_invoice(app, db, associate_org, plan):
    inv, created = svc.create_invoice(associate_org, plan)
    assert created is True
    assert inv.status == 'unpaid'
    assert inv.amount == plan.price
    assert inv.credits == plan.credits
    assert inv.validity_days == plan.validity_days
    assert inv.plan_name == plan.name
    assert inv.number.startswith('INV-')


def test_create_invoice_reuses_unpaid(app, db, associate_org, plan):
    a, created_a = svc.create_invoice(associate_org, plan)
    b, created_b = svc.create_invoice(associate_org, plan)
    assert created_a is True
    assert created_b is False
    assert a.id == b.id


def test_create_invoice_inactive_plan_rejected(app, db,
                                               associate_org, plan):
    plan.is_active = False
    db.session.commit()
    with pytest.raises(svc.BillingError, match='not available'):
        svc.create_invoice(associate_org, plan)


def test_mark_paid_creates_sub_and_credits_wallet(app, db,
                                                  associate_org, plan):
    starting = wallet_svc.get_balance(associate_org.id)
    inv, _ = svc.create_invoice(associate_org, plan)

    invoice, sub = svc.mark_paid(
        inv, actor_id=None,
        payment_method='momo',
        payment_reference='MTN-12345')

    assert invoice.status == 'paid'
    assert invoice.paid_at is not None
    assert invoice.payment_method == 'momo'
    assert invoice.payment_reference == 'MTN-12345'
    assert sub.status == 'active'
    assert sub.plan_id == plan.id
    assert wallet_svc.get_balance(associate_org.id) == starting + plan.credits


def test_mark_paid_snapshots_credit_amount(app, db,
                                           associate_org, plan):
    """If the plan changes after the invoice is issued, the invoice wins."""
    inv, _ = svc.create_invoice(associate_org, plan)
    plan.credits = 99999
    db.session.commit()

    starting = wallet_svc.get_balance(associate_org.id)
    svc.mark_paid(inv, actor_id=None,
                  payment_method='cash', payment_reference='X')

    # Credits granted = invoice snapshot, not the mutated plan
    assert wallet_svc.get_balance(associate_org.id) == starting + inv.credits


def test_mark_paid_expires_previous_subscription(app, db,
                                                 associate_org, plan):
    from app.models import Subscription
    old = Subscription(
        org_id=associate_org.id, plan_id=plan.id,
        starts_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        status='active',
    )
    db.session.add(old)
    db.session.commit()

    inv, _ = svc.create_invoice(associate_org, plan)
    svc.mark_paid(inv, actor_id=None,
                  payment_method='bank', payment_reference='B1')

    db.session.refresh(old)
    assert old.status == 'expired'


def test_mark_paid_rejects_bad_method(app, db, associate_org, plan):
    inv, _ = svc.create_invoice(associate_org, plan)
    with pytest.raises(svc.BillingError, match='Payment method'):
        svc.mark_paid(inv, actor_id=None,
                      payment_method='bitcoin',
                      payment_reference='X')


def test_mark_paid_rejects_missing_reference(app, db,
                                             associate_org, plan):
    inv, _ = svc.create_invoice(associate_org, plan)
    with pytest.raises(svc.BillingError, match='reference'):
        svc.mark_paid(inv, actor_id=None,
                      payment_method='momo', payment_reference='')


def test_mark_paid_rejects_already_paid(app, db, associate_org, plan):
    inv, _ = svc.create_invoice(associate_org, plan)
    svc.mark_paid(inv, actor_id=None,
                  payment_method='momo', payment_reference='A')
    with pytest.raises(svc.BillingError, match='not unpaid'):
        svc.mark_paid(inv, actor_id=None,
                      payment_method='momo', payment_reference='B')


def test_cancel_unpaid_invoice(app, db, associate_org, plan):
    inv, _ = svc.create_invoice(associate_org, plan)
    svc.cancel_invoice(inv, actor_id=None, reason='client changed mind')
    assert inv.status == 'cancelled'
    assert inv.cancellation_reason == 'client changed mind'


def test_cancel_paid_invoice_rejected(app, db, associate_org, plan):
    inv, _ = svc.create_invoice(associate_org, plan)
    svc.mark_paid(inv, actor_id=None,
                  payment_method='cash', payment_reference='X')
    with pytest.raises(svc.BillingError, match='Only unpaid'):
        svc.cancel_invoice(inv, actor_id=None, reason='oops')


def test_ledger_invariant_after_mark_paid(app, db, associate_org, plan):
    from app.models import WalletTransaction
    inv, _ = svc.create_invoice(associate_org, plan)
    svc.mark_paid(inv, actor_id=None,
                  payment_method='momo', payment_reference='X')

    total = (db.session.query(
                db.func.coalesce(db.func.sum(WalletTransaction.delta), 0))
             .filter_by(org_id=associate_org.id).scalar()) or 0
    last = (WalletTransaction.query
            .filter_by(org_id=associate_org.id)
            .order_by(WalletTransaction.id.desc()).first())
    assert int(total) == int(last.balance_after)