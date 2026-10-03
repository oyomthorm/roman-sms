from flask import (Blueprint, render_template, redirect, url_for,
                   flash, current_app)
from flask_login import login_required, current_user

from app.services import billing as billing_svc
from app.services import plans as plans_svc
from app.services import subscriptions as subs_svc
from app.services.wallet import get_balance
from app.services.entitlements import current_rate_ugx

billing_bp = Blueprint('billing', __name__)


def _org():
    return current_user.organization


@billing_bp.route('/wallet')
@login_required
def wallet():
    from app.models import WalletTransaction
    org = _org()
    txns = (WalletTransaction.query
            .filter_by(org_id=org.id)
            .order_by(WalletTransaction.id.desc())
            .limit(100).all())
    invoices = billing_svc.list_for_org(org, limit=30)
    sub = subs_svc.current_for(org.id)

    balance = get_balance(org.id)
    rate = current_rate_ugx(org.id)

    return render_template(
        'billing/wallet.html',
        balance=balance,
        rate_ugx=rate,
        balance_value_ugx=balance * rate,
        transactions=txns,
        invoices=invoices,
        subscription=sub,
    )


@billing_bp.route('/plans')
@login_required
def plans():
    items = plans_svc.list_for_pricing()
    featured = plans_svc.get_featured()
    return render_template('billing/plans.html',
                           plans=items,
                           featured=featured)


@billing_bp.route('/plans/<int:pid>/buy', methods=['POST'])
@login_required
def buy(pid):
    org = _org()
    plan = plans_svc.get(pid)
    if not plan or not plan.is_active:
        flash('That plan is not available.', 'danger')
        return redirect(url_for('billing.plans'))

    invoice, created = billing_svc.create_invoice(
        org, plan, actor_id=current_user.id)

    if created:
        flash(f'Invoice {invoice.number} created for '
              f'UGX {invoice.amount:,.0f}. Follow the payment '
              f'instructions below.', 'info')
    else:
        flash(f'You already have an unpaid invoice for {plan.name}.',
              'info')
    return redirect(url_for('billing.invoice', invoice_id=invoice.id))


@billing_bp.route('/invoices/<int:invoice_id>')
@login_required
def invoice(invoice_id):
    inv = billing_svc.get_for_org(_org(), invoice_id)
    if not inv:
        return render_template('errors/404.html'), 404
    return render_template(
        'billing/invoice.html',
        invoice=inv,
        payment_instructions=current_app.config.get(
            'PAYMENT_INSTRUCTIONS', ''),
    )