from datetime import datetime
from app.extensions import db


class CampaignSchedule(db.Model):
    """
    A schedule is a list of exact datetimes. Each one fires as its own
    Campaign with its own wallet debit and its own recipient list
    resolved fresh from the current contacts.

    Datetimes are stored in local time (see SCHEDULER_TZ_OFFSET_HOURS)
    as ISO 8601 strings without seconds:

        '["2026-10-15T09:00", "2026-10-20T14:30"]'

    When a time fires, it is removed from the list. When the list is
    empty, the schedule is marked completed.
    """
    __tablename__ = 'campaign_schedule'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey('organization.id', name='fk_schedule_org'),
        nullable=False, index=True)
    created_by = db.Column(
        db.Integer,
        db.ForeignKey('user.id', name='fk_schedule_creator'),
        nullable=True)

    # What to send
    name = db.Column(db.String(150), nullable=False)
    body = db.Column(db.Text, nullable=False)
    template_id = db.Column(
        db.Integer,
        db.ForeignKey('message_template.id', name='fk_schedule_template'),
        nullable=True)
    group_id = db.Column(
        db.Integer,
        db.ForeignKey('contact_group.id', name='fk_schedule_group'),
        nullable=True)
    district_id = db.Column(
        db.Integer,
        db.ForeignKey('district.id', name='fk_schedule_district'),
        nullable=True)
    sender_id = db.Column(db.String(60), nullable=False)

    # JSON list of local datetimes
    scheduled_times = db.Column(db.Text, nullable=False, default='[]')

    # Lifecycle
    status = db.Column(db.String(20), default='active', index=True)
    # active | paused | cancelled | completed
    pause_reason = db.Column(db.String(255))

    # Counters
    next_run_at = db.Column(db.DateTime, index=True)
    last_run_at = db.Column(db.DateTime)
    runs_completed = db.Column(db.Integer, default=0)
    runs_skipped = db.Column(db.Integer, default=0)
    total_sent = db.Column(db.Integer, default=0)
    total_failed = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    org = db.relationship('Organization')
    group = db.relationship('Group')
    district = db.relationship('District')
    template = db.relationship('MessageTemplate')
    creator = db.relationship('User')
    runs = db.relationship('Campaign', backref='schedule',
                           lazy='dynamic',
                           order_by='Campaign.id.desc()')

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def times_list(self):
        import json
        try:
            return json.loads(self.scheduled_times or '[]')
        except (ValueError, TypeError):
            return []

    @property
    def times_display(self):
        """Human label. e.g. '15 Oct 09:00, 20 Oct 14:30'."""
        out = []
        for iso in sorted(self.times_list):
            try:
                dt = datetime.strptime(iso, '%Y-%m-%dT%H:%M')
                out.append(dt.strftime('%d %b %H:%M'))
            except ValueError:
                continue
        return ', '.join(out) if out else '—'

    @property
    def run_count(self):
        """Number of datetimes still pending."""
        return len(self.times_list)

    @property
    def is_active(self):
        return self.status == 'active'