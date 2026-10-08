"""
Append-only wallet ledger.

Two ways credits enter a wallet:

  credit()   — new credits from outside the platform (Pahappa syncs,
               manual master top-ups, refunds of failed sends).
               Only allowed for reasons in EXTERNAL_CREDIT_REASONS.

  transfer() — move credits from one wallet to another. Debits the
               source and credits the target in one transaction.

The distinction is enforced: any credit that isn't tagged as
external must have a source_org_id, and the source is debited in the
same transaction. That keeps the invariant

    SUM(all wallet deltas) == credits held on the platform

honest. See ADR-018.
"""
from app.extensions import db
from app.models import Organization, WalletTransaction


class InsufficientCredits(Exception):
    pass


class WalletError(Exception):
    pass


# Reasons that legitimately create NEW credits in the ledger.
# Anything else requires a source_org_id that is debited atomically.
EXTERNAL_CREDIT_REASONS = {
    'master_opening_balance',   # seed time — mirrors Pahappa
    'master_topup',             # manual top-up from Pahappa
    'pahappa_sync',             # reconciliation with live Pahappa balance
    'refund',                   # reversal of a failed send
    'adjustment',               # dev / test correction
}


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def get_balance(org_id):
    last = (WalletTransaction.query
            .filter_by(org_id=org_id)
            .order_by(WalletTransaction.id.desc())
            .first())
    return last.balance_after if last else 0


def recompute_balance(org_id):
    total = (db.session.query(
                db.func.coalesce(db.func.sum(WalletTransaction.delta), 0))
             .filter_by(org_id=org_id).scalar())
    return int(total or 0)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def credit(org_id, amount, reason, reference=None, note=None,
           actor_id=None, source_org_id=None):
    """
    Add credits to a wallet.

    source_org_id: when set, the source wallet is debited by the same
    amount in the same transaction. When None, `reason` must be in
    EXTERNAL_CREDIT_REASONS.
    """
    if amount <= 0:
        raise ValueError('credit amount must be positive')

    if source_org_id is None:
        if reason not in EXTERNAL_CREDIT_REASONS:
            raise WalletError(
                f'Reason {reason!r} requires a source_org_id. '
                f'Allowed without source: '
                f'{sorted(EXTERNAL_CREDIT_REASONS)}'
            )
        return _write_credit(org_id, amount, reason, reference,
                             note, actor_id, source_org_id=None)

    if source_org_id == org_id:
        raise WalletError('Source and target orgs must differ.')

    _lock_orgs(source_org_id, org_id)

    source_balance = get_balance(source_org_id)
    if source_balance < amount:
        raise InsufficientCredits(
            f'Org {source_org_id} has {source_balance}, need {amount}'
        )

    _write_debit(
        source_org_id, amount, reason,
        reference=reference,
        note=(f'{note} -> org {org_id}' if note
              else f'transfer -> org {org_id}'),
        actor_id=actor_id,
    )

    return _write_credit(org_id, amount, reason, reference,
                         note, actor_id, source_org_id=source_org_id)


def debit(org_id, amount, reason, reference=None, note=None,
          actor_id=None):
    """Debit a wallet. No source tracking — debits consume credits."""
    if amount <= 0:
        raise ValueError('debit amount must be positive')

    _lock_orgs(org_id)
    bal = get_balance(org_id)
    if bal < amount:
        raise InsufficientCredits(f'Need {amount}, have {bal}')

    return _write_debit(org_id, amount, reason, reference, note,
                        actor_id)


def transfer(from_org_id, to_org_id, amount, *, reason,
             reference=None, note=None, actor_id=None):
    """Explicit internal transfer. Same as credit() with a source."""
    return credit(to_org_id, amount, reason,
                  reference=reference, note=note, actor_id=actor_id,
                  source_org_id=from_org_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def master_org_id():
    """The master org's id. Raises if the master org is missing."""
    master = Organization.query.filter_by(is_master=True).first()
    if not master:
        raise WalletError('Master org missing. Run seed.')
    return master.id


def _lock_orgs(*org_ids):
    """
    Lock the given orgs in ascending id order so concurrent
    transfers that touch the same orgs serialize without deadlocking.
    """
    ordered = sorted(set(org_ids))
    locked = {}
    for oid in ordered:
        org = (Organization.query
               .filter_by(id=oid)
               .with_for_update()
               .first())
        if org:
            locked[oid] = org
    return locked


def _write_credit(org_id, amount, reason, reference, note,
                  actor_id, source_org_id=None):
    bal = get_balance(org_id) + amount
    tx = WalletTransaction(
        org_id=org_id, delta=amount, reason=reason,
        reference=reference, note=note,
        balance_after=bal, actor_id=actor_id,
        source_org_id=source_org_id,
    )
    db.session.add(tx)
    db.session.flush()
    return tx


def _write_debit(org_id, amount, reason, reference, note, actor_id):
    bal = get_balance(org_id)
    tx = WalletTransaction(
        org_id=org_id, delta=-amount, reason=reason,
        reference=reference, note=note,
        balance_after=bal - amount, actor_id=actor_id,
    )
    db.session.add(tx)
    db.session.flush()
    return tx