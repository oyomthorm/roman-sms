from datetime import datetime
from app.extensions import db


class WalletTransaction(db.Model):
    __tablename__ = 'wallet_transaction'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'),
                       nullable=False, index=True)
    delta = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(40), nullable=False)
    reference = db.Column(db.String(80))
    balance_after = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(255))
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    source_org_id = db.Column(
        db.Integer,
        db.ForeignKey('organization.id',
                      name='fk_wallet_source_org'),
        nullable=True,
        index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.Index('ix_wallet_org_created', 'org_id', 'created_at'),
    )



class Invoice(db.Model):
    __tablename__ = 'invoice'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'),
                       nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'))

    number = db.Column(db.String(40), nullable=False, index=True)
    status = db.Column(db.String(20), default='unpaid', index=True)

    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default='UGX')
    credits = db.Column(db.Integer, default=0, nullable=False)
    validity_days = db.Column(db.Integer, default=30, nullable=False)
    plan_name = db.Column(db.String(100))

    issued_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    paid_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)

    payment_method = db.Column(db.String(40))
    payment_reference = db.Column(db.String(120))
    marked_paid_by = db.Column(db.Integer, db.ForeignKey('user.id'))

    cancelled_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    cancellation_reason = db.Column(db.String(255))

    note = db.Column(db.String(255))

    plan = db.relationship('Plan')
    org = db.relationship('Organization')

    __table_args__ = (
        db.UniqueConstraint('number', name='uq_invoice_number'),
    )