from datetime import datetime
from app.extensions import db


class SignupRequest(db.Model):
    """
    An application to open an associate account.

    Deliberately separate from Organization. A pending signup is not a
    tenant — it has no wallet, no contacts, no data. On approval, we
    create the Organization and User from this record and link back.
    """
    __tablename__ = 'signup_request'
    id = db.Column(db.Integer, primary_key=True)

    # Business details
    company_name = db.Column(db.String(150), nullable=False)
    desired_slug = db.Column(db.String(60), nullable=False, index=True)
    brand_name = db.Column(db.String(60), nullable=False)
    district_id = db.Column(
        db.Integer,
        db.ForeignKey('district.id', name='fk_signup_district'),
        nullable=True, index=True)

    # Contact person (becomes the associate admin)
    contact_name = db.Column(db.String(120), nullable=False)
    contact_email = db.Column(db.String(150), nullable=False, index=True)
    contact_phone = db.Column(db.String(20))

    # Intent
    plan_id = db.Column(
        db.Integer,
        db.ForeignKey('plan.id', name='fk_signup_plan'),
        nullable=True)
    expected_volume = db.Column(db.String(40))   # informational
    message = db.Column(db.Text)                 # free text

    # Lifecycle
    status = db.Column(db.String(20), default='pending', index=True)
    # pending | approved | rejected | spam

    reviewed_by = db.Column(
        db.Integer,
        db.ForeignKey('user.id', name='fk_signup_reviewer'),
        nullable=True)
    reviewed_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.String(255))

    # Link to the org/user created on approval
    created_org_id = db.Column(
        db.Integer,
        db.ForeignKey('organization.id', name='fk_signup_org'),
        nullable=True)
    created_user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', name='fk_signup_user'),
        nullable=True)

    # Abuse tracking
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow,
                           index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    district = db.relationship('District')
    plan = db.relationship('Plan')

    __table_args__ = (
        db.Index('ix_signup_status_created', 'status', 'created_at'),
    )

    @property
    def is_pending(self):
        return self.status == 'pending'