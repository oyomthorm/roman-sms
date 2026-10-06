from datetime import datetime, timedelta

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, Response)
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.models import (Organization, User, Plan, Campaign, MessageLog,
                        AuditLog, SendQueue, WalletTransaction,
                        Invoice, PoolPermission, PoolContact,
                        SignupRequest)
from app.permissions import master_required
from app.services import orgs as orgs_svc
from app.services import plans as plans_svc
from app.services import subscriptions as subs_svc
from app.services import wallet as wallet_svc
from app.services import billing as billing_svc
from app.services import pool as pool_svc
from app.services import geo as geo_svc
from app.services import signups as signup_svc
from app.services import ratelimit
from app.services.entitlements import current_rate_ugx
from app.services.renderer import with_prefix, segments
from app.services.audit import log as audit
from app.services import invoice_pdf

from app.services import pahappa_balance

master_bp = Blueprint('master', __name__)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _balances(orgs):
    return {o.id: wallet_svc.get_balance(o.id) for o in orgs}


def _rate_map(orgs):
    """UGX per credit for each org, keyed by org id."""
    return {o.id: current_rate_ugx(o.id) for o in orgs}

def _system_sender_org():
    return Organization.query.filter_by(is_system=True).first()


def _compute_margin(org_id, active_sub, days=30):
    """
    Return a dict with retail billed (in UGX), wholesale cost (in UGX),
    and the difference. All figures from the last `days` days.

    retail_billed is derived from wallet debits with reason='sms_send'
    multiplied by the org's current plan rate.
    wholesale is the sum of provider_cost on messages we actually sent.
    """
    since = datetime.utcnow() - timedelta(days=days)

    retail_credits = -int((db.session.query(
                             func.coalesce(
                                 func.sum(WalletTransaction.delta), 0))
                           .filter_by(org_id=org_id, reason='sms_send')
                           .filter(WalletTransaction.created_at >= since)
                           .scalar()) or 0)

    wholesale = float((db.session.query(
                         func.coalesce(
                             func.sum(MessageLog.provider_cost), 0))
                       .filter_by(org_id=org_id)
                       .filter(MessageLog.sent_at >= since)
                       .scalar()) or 0)

    rate = 0.0
    if active_sub and active_sub.plan and active_sub.plan.rate_per_sms:
        rate = float(active_sub.plan.rate_per_sms)

    retail_ugx = float(retail_credits) * rate

    return {
        'retail': retail_ugx,
        'wholesale': wholesale,
        'value': retail_ugx - wholesale,
        'days': days,
    }


# ----------------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------------

@master_bp.route('/')
@login_required
@master_required
def index():
    orgs = orgs_svc.list_associates()
    since = datetime.utcnow() - timedelta(days=30)

    sent_30d = (MessageLog.query.filter_by(status='sent')
                .filter(MessageLog.sent_at >= since).count())
    failed_30d = (MessageLog.query.filter_by(status='failed')
                  .filter(MessageLog.created_at >= since).count())
    queued = SendQueue.query.filter_by(status='pending').count()

    balances = _balances(orgs)
    total_credits = sum(balances.values())

    recent_audit = (AuditLog.query
                    .order_by(AuditLog.id.desc())
                    .limit(15).all())

    # Master org's own wallet — the operator's internal balance
    master_org = Organization.query.filter_by(is_master=True).first()
    master_wallet = wallet_svc.get_balance(master_org.id) if master_org else 0

    # Live Pahappa balance
    pahappa = pahappa_balance.current()
    drift = None
    if pahappa['balance'] is not None:
        drift = master_wallet - pahappa['balance']

    return render_template(
        'master/index.html',
        orgs=orgs,
        balances=balances,
        stats={
            'orgs': len(orgs),
            'active': sum(1 for o in orgs if o.status == 'active'),
            'suspended': sum(1 for o in orgs if o.status == 'suspended'),
            'credits_outstanding': total_credits,
            'sent_30d': sent_30d,
            'failed_30d': failed_30d,
            'queued': queued,
        },
        recent_audit=recent_audit,
        master_wallet=master_wallet,
        pahappa=pahappa,
        drift=drift,
    )

# ----------------------------------------------------------------------
# Organizations
# ----------------------------------------------------------------------

@master_bp.route('/orgs')
@login_required
@master_required
def orgs():
    items = orgs_svc.list_associates()
    return render_template('master/orgs.html',
                           orgs=items,
                           balances=_balances(items),
                           rate_map=_rate_map(items))


@master_bp.route('/orgs/new', methods=['GET', 'POST'])
@login_required
@master_required
def org_new():
    if request.method == 'POST':
        district_id_raw = request.form.get('district_id', '').strip()
        district_id = int(district_id_raw) if district_id_raw.isdigit() else None
        try:
            org, admin = orgs_svc.create_associate(
                name=request.form.get('name', ''),
                slug=request.form.get('slug', ''),
                brand_name=request.form.get('brand_name', ''),
                admin_email=request.form.get('admin_email', ''),
                admin_password=request.form.get('admin_password', ''),
                admin_full_name=request.form.get('admin_full_name', ''),
                contact_email=request.form.get('contact_email', ''),
                contact_phone=request.form.get('contact_phone', ''),
                district_id=district_id,
                actor_id=current_user.id,
            )
        except orgs_svc.OrgError as e:
            flash(str(e), 'danger')
            return render_template('master/org_form.html',
                                   org=None, form=request.form,
                                   districts_by_region=geo_svc.list_by_region())
        flash(f'Created {org.name}. Admin: {admin.email}', 'success')
        return redirect(url_for('master.org_detail', oid=org.id))

    return render_template('master/org_form.html',
                           org=None, form={},
                           districts_by_region=geo_svc.list_by_region())


@master_bp.route('/orgs/<int:oid>')
@login_required
@master_required
def org_detail(oid):
    org = orgs_svc.get_associate_or_404(oid)
    if not org:
        return render_template('errors/404.html'), 404

    ledger = (WalletTransaction.query.filter_by(org_id=org.id)
              .order_by(WalletTransaction.id.desc()).limit(40).all())
    subs = subs_svc.history_for(org.id)
    active_sub = subs_svc.current_for(org.id)
    users = (User.query.filter_by(org_id=org.id)
             .order_by(User.id).all())
    campaigns = (Campaign.query.filter_by(org_id=org.id)
                 .order_by(Campaign.id.desc()).limit(10).all())
    plans = plans_svc.list_active()

    margin = _compute_margin(org.id, active_sub, days=30)

    balance = wallet_svc.get_balance(org.id)
    rate = current_rate_ugx(org.id)

    return render_template(
        'master/org_detail.html',
        org=org,
        balance=balance,
        balance_ugx=balance * rate,
        rate_ugx=rate,
        ledger=ledger, subs=subs, active_sub=active_sub,
        users=users, campaigns=campaigns, plans=plans,
        status=ratelimit.check(org),
        margin=margin,
    )


@master_bp.route('/orgs/<int:oid>/edit', methods=['GET', 'POST'])
@login_required
@master_required
def org_edit(oid):
    org = orgs_svc.get_associate_or_404(oid)
    if not org:
        return render_template('errors/404.html'), 404

    if request.method == 'POST':
        district_id_raw = request.form.get('district_id', '').strip()
        district_id = int(district_id_raw) if district_id_raw.isdigit() else None
        try:
            orgs_svc.update_associate(
                org,
                name=request.form.get('name', ''),
                brand_name=request.form.get('brand_name', ''),
                contact_email=request.form.get('contact_email', ''),
                contact_phone=request.form.get('contact_phone', ''),
                district_id=district_id,
                actor_id=current_user.id,
            )
        except orgs_svc.OrgError as e:
            flash(str(e), 'danger')
        else:
            flash('Organization updated.', 'success')
            return redirect(url_for('master.org_detail', oid=org.id))

    return render_template('master/org_form.html',
                           org=org, form={},
                           districts_by_region=geo_svc.list_by_region())


@master_bp.route('/orgs/<int:oid>/suspend', methods=['POST'])
@login_required
@master_required
def org_suspend(oid):
    org = orgs_svc.get_associate_or_404(oid)
    if not org:
        return render_template('errors/404.html'), 404
    try:
        orgs_svc.suspend_associate(
            org, actor_id=current_user.id,
            reason=request.form.get('reason', '').strip() or None)
    except orgs_svc.OrgError as e:
        flash(str(e), 'danger')
    else:
        flash(f'{org.name} suspended. Pending sends cancelled.', 'warning')
    return redirect(url_for('master.org_detail', oid=org.id))


@master_bp.route('/orgs/<int:oid>/activate', methods=['POST'])
@login_required
@master_required
def org_activate(oid):
    org = orgs_svc.get_associate_or_404(oid)
    if not org:
        return render_template('errors/404.html'), 404
    try:
        orgs_svc.activate_associate(org, actor_id=current_user.id)
    except orgs_svc.OrgError as e:
        flash(str(e), 'danger')
    else:
        flash(f'{org.name} activated.', 'success')
    return redirect(url_for('master.org_detail', oid=org.id))


@master_bp.route('/orgs/<int:oid>/grant', methods=['POST'])
@login_required
@master_required
def org_grant(oid):
    org = orgs_svc.get_associate_or_404(oid)
    if not org:
        return render_template('errors/404.html'), 404

    try:
        amount = int(request.form.get('amount', '0'))
    except ValueError:
        amount = 0
    note = request.form.get('note', '').strip()

    if amount <= 0:
        flash('Amount must be a positive integer.', 'danger')
        return redirect(url_for('master.org_detail', oid=org.id))

    wallet_svc.credit(org.id, amount, reason='manual_topup',
                      note=note or None, actor_id=current_user.id)
    db.session.commit()
    audit('wallet_grant', f'org={org.slug} amount={amount}',
          org_id=org.id, actor_id=current_user.id)
    flash(f'Granted {amount} SMS. Balance: '
          f'{wallet_svc.get_balance(org.id)}.', 'success')
    return redirect(url_for('master.org_detail', oid=org.id))


@master_bp.route('/orgs/<int:oid>/plan', methods=['POST'])
@login_required
@master_required
def org_assign_plan(oid):
    org = orgs_svc.get_associate_or_404(oid)
    if not org:
        return render_template('errors/404.html'), 404

    try:
        plan_id = int(request.form.get('plan_id', '0'))
    except ValueError:
        plan_id = 0
    plan = plans_svc.get(plan_id)
    if not plan:
        flash('Plan not found.', 'danger')
        return redirect(url_for('master.org_detail', oid=org.id))

    duration_raw = request.form.get('duration_days', '').strip()
    try:
        duration = int(duration_raw) if duration_raw else None
    except ValueError:
        duration = None

    credit_wallet = request.form.get('credit_wallet', '1') == '1'

    try:
        subs_svc.grant(
            org, plan,
            duration_days=duration,
            actor_id=current_user.id,
            credit_wallet=credit_wallet,
        )
    except subs_svc.SubscriptionError as e:
        flash(str(e), 'danger')
        return redirect(url_for('master.org_detail', oid=org.id))

    granted = plan.credits if credit_wallet else 0
    duration_label = duration or plan.validity_days or 'no expiry'
    flash(f'Granted {plan.name} for {duration_label}'
          f'{f", credited {granted} SMS" if granted else ""}.', 'success')
    return redirect(url_for('master.org_detail', oid=org.id))


@master_bp.route('/orgs/<int:oid>/users/<int:uid>/reset',
                 methods=['POST'])
@login_required
@master_required
def user_reset_password(oid, uid):
    org = orgs_svc.get_associate_or_404(oid)
    if not org:
        return render_template('errors/404.html'), 404
    new_pw = request.form.get('new_password', '')
    try:
        user = orgs_svc.reset_admin_password(
            org, uid, new_pw, actor_id=current_user.id)
    except orgs_svc.OrgError as e:
        flash(str(e), 'danger')
    else:
        flash(f'Password reset for {user.email}.', 'success')
    return redirect(url_for('master.org_detail', oid=org.id))


# ----------------------------------------------------------------------
# Plans
# ----------------------------------------------------------------------

@master_bp.route('/plans')
@login_required
@master_required
def plans():
    return render_template('master/plans.html',
                           plans=plans_svc.list_all())


@master_bp.route('/plans/new', methods=['GET', 'POST'])
@login_required
@master_required
def plan_new():
    if request.method == 'POST':
        try:
            plans_svc.create_plan(
                name=request.form.get('name', ''),
                price=request.form.get('price', 0),
                currency=request.form.get('currency', 'UGX'),
                credits=request.form.get('credits', 0),
                validity_days=request.form.get('validity_days') or None,
                max_contacts=request.form.get('max_contacts'),
                max_per_minute=request.form.get('max_per_minute', 60),
                max_per_day=request.form.get('max_per_day', 5000),
                tier_min=request.form.get('tier_min') or None,
                tier_max=request.form.get('tier_max') or None,
                sort_order=request.form.get('sort_order', 0),
                is_featured=bool(request.form.get('is_featured')),
                actor_id=current_user.id,
            )
        except plans_svc.PlanError as e:
            flash(str(e), 'danger')
            return render_template('master/plan_form.html',
                                   plan=None, form=request.form)
        flash('Plan created.', 'success')
        return redirect(url_for('master.plans'))
    return render_template('master/plan_form.html', plan=None, form={})


@master_bp.route('/plans/<int:pid>/edit', methods=['GET', 'POST'])
@login_required
@master_required
def plan_edit(pid):
    plan = plans_svc.get(pid)
    if not plan:
        return render_template('errors/404.html'), 404

    if request.method == 'POST':
        try:
            plans_svc.update_plan(
                plan,
                name=request.form.get('name', ''),
                price=request.form.get('price', 0),
                currency=request.form.get('currency', 'UGX'),
                credits=request.form.get('credits', 0),
                validity_days=request.form.get('validity_days') or None,
                max_contacts=request.form.get('max_contacts'),
                max_per_minute=request.form.get('max_per_minute', 60),
                max_per_day=request.form.get('max_per_day', 5000),
                tier_min=request.form.get('tier_min') or None,
                tier_max=request.form.get('tier_max') or None,
                sort_order=request.form.get('sort_order', 0),
                is_featured=bool(request.form.get('is_featured')),
                actor_id=current_user.id,
            )
        except plans_svc.PlanError as e:
            flash(str(e), 'danger')
        else:
            flash('Plan updated.', 'success')
            return redirect(url_for('master.plans'))

    return render_template('master/plan_form.html', plan=plan, form={})


@master_bp.route('/plans/<int:pid>/toggle', methods=['POST'])
@login_required
@master_required
def plan_toggle(pid):
    plan = plans_svc.get(pid)
    if not plan:
        return render_template('errors/404.html'), 404
    plans_svc.toggle_active(plan, actor_id=current_user.id)
    flash(f'Plan {plan.name} is now '
          f'{"active" if plan.is_active else "inactive"}.', 'success')
    return redirect(url_for('master.plans'))


# ----------------------------------------------------------------------
# Invoices
# ----------------------------------------------------------------------

@master_bp.route('/invoices')
@login_required
@master_required
def invoices():
    status = (request.args.get('status') or '').strip()
    org_id = request.args.get('org_id', type=int)

    rows = billing_svc.list_all(
        status=status or None, org_id=org_id, limit=500)

    orgs_by_id = {o.id: o for o in Organization.query.all()}
    user_ids = {r.marked_paid_by for r in rows if r.marked_paid_by}
    users = ({u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()}
             if user_ids else {})

    return render_template('master/invoices.html',
                           rows=rows,
                           orgs_by_id=orgs_by_id,
                           users=users,
                           orgs=orgs_svc.list_associates(),
                           status=status,
                           org_id=org_id or '')


@master_bp.route('/invoices/<int:invoice_id>')
@login_required
@master_required
def invoice_detail(invoice_id):
    inv = billing_svc.get_any(invoice_id)
    if not inv:
        return render_template('errors/404.html'), 404

    paid_by = (User.query.get(inv.marked_paid_by)
               if inv.marked_paid_by else None)
    cancelled_by = (User.query.get(inv.cancelled_by)
                    if inv.cancelled_by else None)
    return render_template('master/invoice_detail.html',
                           invoice=inv,
                           paid_by=paid_by,
                           cancelled_by=cancelled_by)


@master_bp.route('/invoices/<int:invoice_id>/mark-paid',
                 methods=['POST'])
@login_required
@master_required
def invoice_mark_paid(invoice_id):
    inv = billing_svc.get_any(invoice_id)
    if not inv:
        return render_template('errors/404.html'), 404

    method = request.form.get('payment_method', '').strip()
    reference = request.form.get('payment_reference', '').strip()
    duration_raw = request.form.get('duration_days', '').strip()
    note = request.form.get('note', '').strip()

    try:
        duration = int(duration_raw) if duration_raw else None
    except ValueError:
        duration = None

    try:
        invoice, sub = billing_svc.mark_paid(
            inv,
            actor_id=current_user.id,
            payment_method=method,
            payment_reference=reference,
            duration_days=duration,
            note=note or None,
        )
    except billing_svc.BillingError as e:
        flash(str(e), 'danger')
        return redirect(url_for('master.invoice_detail',
                                invoice_id=inv.id))

    if sub:
        flash(f'Invoice {invoice.number} marked paid. '
              f'{invoice.credits} SMS granted, '
              f'plan valid until {sub.expires_at.strftime("%Y-%m-%d")}.',
              'success')
    else:
        flash(f'Invoice {invoice.number} marked paid. '
              f'{invoice.credits} SMS granted.', 'success')
    return redirect(url_for('master.invoice_detail', invoice_id=inv.id))


@master_bp.route('/invoices/<int:invoice_id>/cancel', methods=['POST'])
@login_required
@master_required
def invoice_cancel(invoice_id):
    inv = billing_svc.get_any(invoice_id)
    if not inv:
        return render_template('errors/404.html'), 404

    reason = request.form.get('reason', '').strip()
    try:
        billing_svc.cancel_invoice(inv, actor_id=current_user.id,
                                   reason=reason)
    except billing_svc.BillingError as e:
        flash(str(e), 'danger')
        return redirect(url_for('master.invoice_detail',
                                invoice_id=inv.id))

    flash(f'Invoice {inv.number} cancelled.', 'success')
    return redirect(url_for('master.invoice_detail', invoice_id=inv.id))


@master_bp.route('/orgs/<int:oid>/invoices/new', methods=['POST'])
@login_required
@master_required
def org_new_invoice(oid):
    org = orgs_svc.get_associate_or_404(oid)
    if not org:
        return render_template('errors/404.html'), 404

    plan_id = request.form.get('plan_id', type=int)
    plan = plans_svc.get(plan_id) if plan_id else None
    if not plan:
        flash('Select a plan.', 'danger')
        return redirect(url_for('master.org_detail', oid=org.id))

    try:
        invoice, created = billing_svc.create_invoice(
            org, plan, actor_id=current_user.id,
            note='Issued by master')
    except billing_svc.BillingError as e:
        flash(str(e), 'danger')
        return redirect(url_for('master.org_detail', oid=org.id))

    if created:
        flash(f'Invoice {invoice.number} created for {org.name}.', 'success')
    else:
        flash(f'{org.name} already has an unpaid invoice for '
              f'{plan.name} ({invoice.number}).', 'info')
    return redirect(url_for('master.invoice_detail',
                            invoice_id=invoice.id))


# ----------------------------------------------------------------------
# Audit
# ----------------------------------------------------------------------

@master_bp.route('/audit')
@login_required
@master_required
def audit_view():
    org_id = request.args.get('org_id', type=int)
    action = request.args.get('action', '').strip()

    q = AuditLog.query
    if org_id:
        q = q.filter_by(org_id=org_id)
    if action:
        q = q.filter(AuditLog.action.ilike(f'%{action}%'))

    rows = q.order_by(AuditLog.id.desc()).limit(300).all()

    actor_ids = {r.actor_id for r in rows if r.actor_id}
    actors = {}
    if actor_ids:
        for u in User.query.filter(User.id.in_(actor_ids)).all():
            actors[u.id] = u.email

    return render_template('master/audit.html',
                           rows=rows, actors=actors,
                           orgs=orgs_svc.list_associates(),
                           org_id=org_id or '', action=action)


# ----------------------------------------------------------------------
# Pool
# ----------------------------------------------------------------------

@master_bp.route('/pool')
@login_required
@master_required
def pool():
    district_id = request.args.get('district_id', type=int)
    source_org_id = request.args.get('source_org_id', type=int)
    group_name = (request.args.get('group_name') or '').strip() or None

    stats = pool_svc.pool_stats()
    contacts = pool_svc.list_pool_contacts(
        district_id=district_id,
        source_org_id=source_org_id,
        group_name=group_name,
        limit=500,
    )

    districts_by_region = geo_svc.list_by_region()
    groups = pool_svc.list_pool_groups()

    grants = (PoolPermission.query
              .filter_by(status='active')
              .all())

    orgs_by_id = {o.id: o for o in Organization.query.all()}

    platform = _system_sender_org()
    master_balance = (wallet_svc.get_balance(platform.id)
                      if platform else 0)

    return render_template(
        'master/pool.html',
        stats=stats,
        contacts=contacts,
        districts_by_region=districts_by_region,
        groups=groups,
        grants=grants,
        orgs_by_id=orgs_by_id,
        district_id=district_id,
        source_org_id=source_org_id,
        group_name=group_name,
        master_balance=master_balance,
    )


@master_bp.route('/pool/grants')
@login_required
@master_required
def pool_grants():
    rows = (PoolPermission.query
            .order_by(PoolPermission.granted_at.desc())
            .all())
    orgs_by_id = {o.id: o for o in Organization.query.all()}
    users_by_id = {u.id: u for u in User.query.all()}
    return render_template('master/pool_grants.html',
                           rows=rows,
                           orgs_by_id=orgs_by_id,
                           users_by_id=users_by_id)


@master_bp.route('/pool/send', methods=['GET', 'POST'])
@login_required
@master_required
def pool_send():
    districts_by_region = geo_svc.list_by_region()
    groups = pool_svc.list_pool_groups()

    if request.method == 'POST':
        district_id = request.form.get('district_id', type=int)
        group_name = (request.form.get('group_name') or '').strip() or None
        body = (request.form.get('body') or '').strip()
        name = (request.form.get('name') or 'Pool campaign').strip()

        if not body:
            flash('Message body is required.', 'danger')
            return redirect(url_for('master.pool_send'))

        sender_org = _system_sender_org()
        if not sender_org:
            flash('System sender org missing. Run seed.', 'danger')
            return redirect(url_for('master.pool'))

        recipients = pool_svc.unique_recipients(
            district_id=district_id, group_name=group_name)
        if not recipients:
            flash('No eligible recipients for that filter.', 'danger')
            return redirect(url_for('master.pool_send'))

        rendered = [(r, with_prefix(sender_org, body)) for r in recipients]
        total_segments = sum(segments(msg) for _, msg in rendered)

        campaign = Campaign(
            org_id=sender_org.id, name=name, body=body,
            sender_id=sender_org.brand_name, status='queued',
            total=len(rendered), created_by=current_user.id,
            group_filter=group_name,
        )
        db.session.add(campaign)
        db.session.flush()

        try:
            wallet_svc.debit(
                sender_org.id, total_segments, reason='sms_send',
                reference=f'campaign:{campaign.id}',
                note=f'Pool send: {len(rendered)} recipients',
                actor_id=current_user.id,
            )
        except wallet_svc.InsufficientCredits as e:
            db.session.rollback()
            flash(f'Not enough credits in the platform wallet. {e}',
                  'danger')
            return redirect(url_for('master.pool'))

        campaign.credits_debited = total_segments

        for r, msg in rendered:
            db.session.add(MessageLog(
                org_id=sender_org.id, campaign_id=campaign.id,
                contact_id=None, phone=r.phone, body=msg,
                status='pending',
            ))

        db.session.add(SendQueue(
            campaign_id=campaign.id, org_id=sender_org.id,
            status='pending', run_after=datetime.utcnow(),
        ))

        db.session.commit()
        audit('pool_campaign_queued',
              f'id={campaign.id} recipients={len(rendered)} '
              f'segments={total_segments}')

        flash(f'Pool campaign queued: {len(rendered)} recipients, '
              f'{total_segments} SMS.', 'success')
        return redirect(url_for('master.pool'))

    return render_template('master/pool_send.html',
                           districts_by_region=districts_by_region,
                           groups=groups)


# ----------------------------------------------------------------------
# Platform sender org
# ----------------------------------------------------------------------

@master_bp.route('/platform')
@login_required
@master_required
def platform():
    org = _system_sender_org()
    if not org:
        flash('System sender org missing. Run seed.', 'danger')
        return redirect(url_for('master.index'))

    ledger = (WalletTransaction.query
              .filter_by(org_id=org.id)
              .order_by(WalletTransaction.id.desc())
              .limit(40).all())

    campaigns = (Campaign.query
                 .filter_by(org_id=org.id)
                 .order_by(Campaign.id.desc())
                 .limit(20).all())

    sent_total = (MessageLog.query
                  .filter_by(org_id=org.id, status='sent')
                  .count())

    sent_30d = (MessageLog.query
                .filter_by(org_id=org.id, status='sent')
                .filter(MessageLog.sent_at
                        >= datetime.utcnow() - timedelta(days=30))
                .count())

    return render_template('master/platform.html',
                           org=org,
                           balance=wallet_svc.get_balance(org.id),
                           ledger=ledger,
                           campaigns=campaigns,
                           sent_total=sent_total,
                           sent_30d=sent_30d)


@master_bp.route('/platform/topup', methods=['POST'])
@login_required
@master_required
def platform_topup():
    org = _system_sender_org()
    if not org:
        flash('System sender org missing.', 'danger')
        return redirect(url_for('master.index'))

    try:
        amount = int(request.form.get('amount', '0'))
    except ValueError:
        amount = 0

    if amount <= 0:
        flash('Amount must be positive.', 'danger')
        return redirect(url_for('master.platform'))

    wallet_svc.credit(org.id, amount,
                      reason='master_topup',
                      note=request.form.get('note', '').strip() or None,
                      actor_id=current_user.id)
    db.session.commit()
    audit('platform_topup', f'amount={amount}', actor_id=current_user.id)

    flash(f'Added {amount} SMS. Balance: '
          f'{wallet_svc.get_balance(org.id)}.', 'success')
    return redirect(url_for('master.platform'))


# ----------------------------------------------------------------------
# Signups
# ----------------------------------------------------------------------

@master_bp.route('/signups')
@login_required
@master_required
def signups():
    status = (request.args.get('status') or 'pending').strip()
    if status == 'all':
        rows = signup_svc.list_requests(status=None)
    else:
        rows = signup_svc.list_requests(status=status)

    counts = {
        'pending': signup_svc.pending_count(),
        'approved': SignupRequest.query.filter_by(
            status='approved').count(),
        'rejected': SignupRequest.query.filter_by(
            status='rejected').count(),
        'spam': SignupRequest.query.filter_by(status='spam').count(),
    }

    return render_template('master/signups.html',
                           rows=rows, counts=counts, status=status)


@master_bp.route('/signups/<int:rid>')
@login_required
@master_required
def signup_detail(rid):
    req = signup_svc.get(rid)
    if not req:
        return render_template('errors/404.html'), 404

    districts_by_region = geo_svc.list_by_region()
    return render_template('master/signup_detail.html',
                           req=req,
                           districts_by_region=districts_by_region)


@master_bp.route('/signups/<int:rid>/approve', methods=['POST'])
@login_required
@master_required
def signup_approve(rid):
    req = signup_svc.get(rid)
    if not req:
        return render_template('errors/404.html'), 404

    try:
        credits = int(request.form.get('starter_credits') or 0)
    except ValueError:
        credits = None

    try:
        org, user, granted = signup_svc.approve(
            req, actor=current_user, starter_credits=credits)
    except signup_svc.SignupError as e:
        flash(str(e), 'danger')
        return redirect(url_for('master.signup_detail', rid=rid))

    flash(f'Approved {org.name}. Welcome email sent to {user.email}. '
          f'{granted} starter SMS granted.', 'success')
    return redirect(url_for('master.org_detail', oid=org.id))


@master_bp.route('/signups/<int:rid>/reject', methods=['POST'])
@login_required
@master_required
def signup_reject(rid):
    req = signup_svc.get(rid)
    if not req:
        return render_template('errors/404.html'), 404

    reason = request.form.get('reason', '').strip()
    try:
        signup_svc.reject(req, actor=current_user, reason=reason)
    except signup_svc.SignupError as e:
        flash(str(e), 'danger')
        return redirect(url_for('master.signup_detail', rid=rid))

    flash(f'Rejected {req.company_name}.', 'success')
    return redirect(url_for('master.signups'))


@master_bp.route('/signups/<int:rid>/spam', methods=['POST'])
@login_required
@master_required
def signup_spam(rid):
    req = signup_svc.get(rid)
    if not req:
        return render_template('errors/404.html'), 404
    try:
        signup_svc.mark_spam(req, actor=current_user)
    except signup_svc.SignupError as e:
        flash(str(e), 'danger')
    else:
        flash('Marked as spam.', 'success')
    return redirect(url_for('master.signups'))


@master_bp.route('/invoices/<int:invoice_id>.pdf')
@login_required
@master_required
def invoice_pdf_download(invoice_id):
    """Download any invoice as a PDF."""
    inv = billing_svc.get_any(invoice_id)
    if not inv:
        return render_template('errors/404.html'), 404

    pdf_bytes = invoice_pdf.render_invoice(inv)
    filename = f'{inv.number}.pdf'
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(len(pdf_bytes)),
        },
    )
    
    
@master_bp.route('/platform/sync-pahappa', methods=['POST'])
@login_required
@master_required
def platform_sync_pahappa():
    """
    Bring the master wallet in line with Pahappa's live balance.

    Writes a single compensating ledger row (credit or debit) so the
    wallet equals Pahappa. Append-only — no rows are edited.
    """
    master_org = Organization.query.filter_by(is_master=True).first()
    if not master_org:
        flash('Master org missing. Run seed.', 'danger')
        return redirect(url_for('master.index'))

    # Force a fresh fetch — do not use the cached value for a sync
    pahappa_balance.invalidate()
    pahappa = pahappa_balance.current()

    if pahappa['balance'] is None:
        flash(f'Could not reach Pahappa: {pahappa["error"]}', 'danger')
        return redirect(url_for('master.index'))

    wallet = wallet_svc.get_balance(master_org.id)
    delta = pahappa['balance'] - wallet

    if delta == 0:
        flash('Master wallet already matches Pahappa.', 'info')
        return redirect(url_for('master.index'))

    try:
        if delta > 0:
            wallet_svc.credit(
                master_org.id, delta,
                reason='pahappa_sync',
                note=f'Sync to Pahappa balance ({pahappa["balance"]:,})',
                actor_id=current_user.id,
            )
        else:
            wallet_svc.debit(
                master_org.id, -delta,
                reason='pahappa_sync',
                note=f'Sync to Pahappa balance ({pahappa["balance"]:,})',
                actor_id=current_user.id,
            )
        db.session.commit()

        audit('pahappa_sync',
              f'master wallet {wallet:,} -> {pahappa["balance"]:,} '
              f'(delta {delta:+,})',
              org_id=master_org.id, actor_id=current_user.id)

        flash(f'Master wallet synced. '
              f'{"+" if delta > 0 else ""}{delta:,} credits.', 'success')

    except wallet_svc.InsufficientCredits:
        db.session.rollback()
        flash('Sync failed: wallet has less than needed for the debit.',
              'danger')

    return redirect(url_for('master.index'))