from datetime import datetime
from app.extensions import db


class PoolPermission(db.Model):
    """
    An associate organization's recorded grant of permission to share
    its contact list with the master pool.

    We keep a snapshot of the agreement text and a version marker, so
    we can prove what the associate agreed to, and when.
    """
    __tablename__ = 'pool_permission'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey('organization.id', name='fk_pool_permission_org'),
        nullable=False, index=True)

    granted_by = db.Column(
        db.Integer,
        db.ForeignKey('user.id', name='fk_pool_permission_granted_by'),
        nullable=False)
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)

    revoked_by = db.Column(
        db.Integer,
        db.ForeignKey('user.id', name='fk_pool_permission_revoked_by'),
        nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)

    status = db.Column(db.String(20), default='active', index=True)
    # 'active' | 'revoked'

    agreement_version = db.Column(db.String(20), default='v1')
    agreement_text = db.Column(db.Text)   # full text at time of grant
    note = db.Column(db.String(255))

    __table_args__ = (
        db.Index('ix_pool_permission_org_status', 'org_id', 'status'),
    )

    org = db.relationship('Organization')


class PoolContact(db.Model):
    """
    A contact that has been shared into the master pool.

    One row per (source_org, phone). The same phone shared by two
    associates creates two rows. When we send a pool campaign, we
    deduplicate by phone before sending.

    Revoking an organization's permission deletes its rows.
    """
    __tablename__ = 'pool_contact'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(120))
    # Group name snapshotted from the source Contact at contribution time.
    # Nullable — most contacts do not have a group.
    group_name = db.Column(db.String(80), index=True)
    district_id = db.Column(
        db.Integer,
        db.ForeignKey('district.id', name='fk_pool_contact_district'),
        index=True)
    source_org_id = db.Column(
        db.Integer,
        db.ForeignKey('organization.id', name='fk_pool_contact_source_org'),
        nullable=False, index=True)
    source_contact_id = db.Column(db.Integer)  # not a FK — source may delete
    opted_out = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('source_org_id', 'phone',
                            name='uq_pool_source_phone'),
    )

    source_org = db.relationship('Organization')
    district = db.relationship('District')