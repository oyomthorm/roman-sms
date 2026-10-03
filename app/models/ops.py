from datetime import datetime
from app.extensions import db


class SendQueue(db.Model):
    __tablename__ = 'send_queue'
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'),
                            nullable=False, index=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'),
                       nullable=False, index=True)
    status = db.Column(db.String(20), default='pending', index=True)
    attempts = db.Column(db.Integer, default=0)
    last_error = db.Column(db.Text)
    run_after = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    locked_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)


class OptOut(db.Model):
    """Platform-wide opt-out. Enforced across every org."""
    __tablename__ = 'opt_out'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    reason = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'), index=True)
    action = db.Column(db.String(80), nullable=False)
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    
class NotificationDismissal(db.Model):
    """
    Per-user dismissal of a computed notification.

    Notifications themselves are not stored — they are derived from live
    conditions each render. This table only records that a user has said
    "I have seen this specific condition."

    `key` is a stable identifier computed by the notification service.
    """
    __tablename__ = 'notification_dismissal'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', name='fk_notification_dismissal_user'),
        nullable=False, index=True)
    key = db.Column(db.String(120), nullable=False, index=True)
    dismissed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'key',
                            name='uq_notification_dismissal_user_key'),
    )