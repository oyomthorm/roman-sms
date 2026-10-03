from app.extensions import db
from app.models import Organization, WalletTransaction
from datetime import datetime

class InsufficientCredits(Exception):
    pass


def get_balance(org_id):
    last = (WalletTransaction.query
            .filter_by(org_id=org_id)
            .order_by(WalletTransaction.id.desc())
            .first())
    return last.balance_after if last else 0


def _lock_org(org_id):
    return Organization.query.filter_by(id=org_id).with_for_update().first()


def credit(org_id, amount, reason, reference=None, note=None, actor_id=None):
    if amount <= 0:
        raise ValueError('credit amount must be positive')
    _lock_org(org_id)
    bal = get_balance(org_id) + amount
    tx = WalletTransaction(
        org_id=org_id, delta=amount, reason=reason,
        reference=reference, note=note,
        balance_after=bal, actor_id=actor_id,
    )
    db.session.add(tx)
    db.session.flush()
    return tx


def debit(org_id, amount, reason, reference=None, note=None, actor_id=None):
    if amount <= 0:
        raise ValueError('debit amount must be positive')
    _lock_org(org_id)
    bal = get_balance(org_id)
    if bal < amount:
        raise InsufficientCredits(f'Need {amount}, have {bal}')
    tx = WalletTransaction(
        org_id=org_id, delta=-amount, reason=reason,
        reference=reference, note=note,
        balance_after=bal - amount, actor_id=actor_id,
    )
    db.session.add(tx)
    db.session.flush()
    return tx


def recompute_balance(org_id):
    total = (db.session.query(
                db.func.coalesce(db.func.sum(WalletTransaction.delta), 0))
             .filter_by(org_id=org_id).scalar())
    return int(total or 0)
