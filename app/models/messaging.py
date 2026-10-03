from datetime import datetime
from app.extensions import db


class Group(db.Model):
    __tablename__ = 'contact_group'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'),
                       nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    contacts = db.relationship('Contact', backref='group', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('org_id', 'name', name='uq_org_group_name'),
    )


class Contact(db.Model):
    __tablename__ = 'contact'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'),
                       nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(120))
    # Legacy string column kept for the backfill. Unused by code.
    group_legacy = db.Column('group', db.String(80), index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('contact_group.id'),
                         index=True)
    district_id = db.Column(
        db.Integer,
        db.ForeignKey('district.id', name='fk_contact_district'),
        nullable=True, index=True)
    opted_out = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    district = db.relationship('District')

    __table_args__ = (
        db.UniqueConstraint('org_id', 'phone', name='uq_org_phone'),
    )


class MessageTemplate(db.Model):
    __tablename__ = 'message_template'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'),
                       nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Campaign(db.Model):
    __tablename__ = 'campaign'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'),
                       nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('message_template.id'))
    body = db.Column(db.Text, nullable=False)
    sender_id = db.Column(db.String(60), nullable=False)
    group_filter = db.Column(db.String(80))
    district_filter = db.Column(db.String(80))
    status = db.Column(db.String(20), default='draft', index=True)
    total = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    credits_debited = db.Column(db.Integer, default=0)
    scheduled_at = db.Column(db.DateTime)
    schedule_id = db.Column(
        db.Integer,
        db.ForeignKey('campaign_schedule.id', name='fk_campaign_schedule'),
        nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)


class MessageLog(db.Model):
    __tablename__ = 'message_log'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'),
                       nullable=False, index=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'),
                            index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'))
    phone = db.Column(db.String(20), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending', index=True)
    # status now goes: pending → sent → delivered | delivery_failed
    api_response = db.Column(db.Text)
    provider_ref = db.Column(db.String(120), index=True)
    provider_cost = db.Column(db.Numeric(12, 4))
    delivery_status_raw = db.Column(db.String(40))
    delivered_at = db.Column(db.DateTime)
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)