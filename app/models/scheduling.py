from datetime import datetime
from app.extensions import db


class CampaignSchedule(db.Model):
    """
    A recurring campaign rule.

    The schedule is a template plus a recurrence rule. Each time it
    fires, services.schedules.materialize_run() creates a normal
    Campaign (linked back via Campaign.schedule_id) with its own wallet
    debit and its own recipient list resolved fresh from the current
    contacts.

    Recurrence:
      days_of_week  — comma-separated 3-letter codes, e.g. "mon,wed,fri"
      times_of_day  — JSON array of "HH:MM" strings in local time, e.g.
                      '["09:00", "14:00"]'
      starts_on     — first date the schedule may fire
      ends_on       — last date, or NULL for "runs forever"
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

    # Recurrence rule
    days_of_week = db.Column(db.String(30), nullable=False)
    times_of_day = db.Column(db.Text, nullable=False)  # JSON list of "HH:MM"

    # Active window
    starts_on = db.Column(db.Date, nullable=False)
    ends_on = db.Column(db.Date, nullable=True)  # null = forever

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
    def days_list(self):
        return [d for d in (self.days_of_week or '').split(',') if d]

    @property
    def times_list(self):
        import json
        try:
            return json.loads(self.times_of_day or '[]')
        except (ValueError, TypeError):
            return []

    @property
    def days_label(self):
        """Human label, e.g. 'Mon, Wed, Fri'."""
        names = {'mon': 'Mon', 'tue': 'Tue', 'wed': 'Wed', 'thu': 'Thu',
                 'fri': 'Fri', 'sat': 'Sat', 'sun': 'Sun'}
        return ', '.join(names.get(d, d) for d in self.days_list)

    @property
    def times_label(self):
        return ', '.join(self.times_list)

    @property
    def is_active(self):
        return self.status == 'active'