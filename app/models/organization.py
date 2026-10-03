from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class Organization(db.Model):
    __tablename__ = 'organization'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(60), unique=True, nullable=False, index=True)
    brand_name = db.Column(db.String(60), nullable=False)
    status = db.Column(db.String(20), default='active', index=True)
    is_master = db.Column(db.Boolean, default=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('organization.id'))
    contact_email = db.Column(db.String(150))
    contact_phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    is_system = db.Column(db.Boolean, default=False, index=True)
    
    users = db.relationship('User', backref='organization', lazy='dynamic')

    district_id = db.Column(
        db.Integer,
        db.ForeignKey('district.id', name='fk_organization_district'),
        nullable=True, index=True)

    district = db.relationship('District')
    
    @property
    def prefix(self):
        return f"{self.brand_name}: "


class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120))
    role = db.Column(db.String(30), default='associate_user', index=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'),
                       nullable=False, index=True)
    is_active_flag = db.Column('is_active', db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_active(self):
        return bool(self.is_active_flag)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @property
    def is_master(self):
        return self.role == 'master_admin'

    @property
    def is_org_admin(self):
        return self.role in ('master_admin', 'associate_admin')


class Plan(db.Model):
    __tablename__ = 'plan'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default='UGX')
    credits = db.Column(db.Integer, nullable=False)
    tier_min = db.Column(db.Integer)
    tier_max = db.Column(db.Integer)
    sort_order = db.Column(db.Integer, default=0, index=True)
    is_featured = db.Column(db.Boolean, default=False)
    max_contacts = db.Column(db.Integer)
    max_per_minute = db.Column(db.Integer, default=60)
    max_per_day = db.Column(db.Integer, default=5000)
    validity_days = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def rate_per_sms(self):
        if not self.credits:
            return None
        try:
            return float(self.price) / float(self.credits)
        except (TypeError, ValueError):
            return None

    @property
    def tier_label(self):
        if self.tier_min is None and self.tier_max is None:
            return 'Any volume'
        if self.tier_max is None:
            return f'{self.tier_min:,}+'
        if self.tier_min is None:
            return f'Up to {self.tier_max:,}'
        return f'{self.tier_min:,} – {self.tier_max:,}'
    

class Subscription(db.Model):
    __tablename__ = 'subscription'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'),
                       nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='active', index=True)
    credits_granted = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plan = db.relationship('Plan')