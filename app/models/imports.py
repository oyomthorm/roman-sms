from datetime import datetime
from app.extensions import db


class ContactImport(db.Model):
    """
    A record of one CSV import. Kept permanently so a client can audit
    what happened to a file that was uploaded months ago.
    """
    __tablename__ = 'contact_import'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey('organization.id', name='fk_contact_import_org'),
        nullable=False, index=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', name='fk_contact_import_user'),
        nullable=True)

    # File metadata
    filename = db.Column(db.String(255))
    file_size = db.Column(db.Integer)

    # Options used for this import
    on_duplicate = db.Column(db.String(10), default='skip')
    default_group = db.Column(db.String(80))
    default_district_id = db.Column(
        db.Integer,
        db.ForeignKey('district.id', name='fk_contact_import_district'),
        nullable=True)

    # Counts
    total_rows = db.Column(db.Integer, default=0)
    added = db.Column(db.Integer, default=0)
    updated = db.Column(db.Integer, default=0)
    skipped_duplicate = db.Column(db.Integer, default=0)
    skipped_in_file = db.Column(db.Integer, default=0)
    skipped_opt_out = db.Column(db.Integer, default=0)
    invalid = db.Column(db.Integer, default=0)
    groups_created = db.Column(db.Integer, default=0)
    districts_matched = db.Column(db.Integer, default=0)
    districts_unmatched = db.Column(db.Integer, default=0)
    cap_hit = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    org = db.relationship('Organization')
    user = db.relationship('User')
    default_district = db.relationship('District')
    issues = db.relationship(
        'ContactImportIssue', backref='import_job', lazy='dynamic',
        cascade='all, delete-orphan')

    @property
    def issue_count(self):
        return self.issues.count()

    @property
    def has_issues(self):
        return self.issue_count > 0

    @property
    def effective_rows(self):
        """Rows that landed in the DB (new or updated)."""
        return (self.added or 0) + (self.updated or 0)


class ContactImportIssue(db.Model):
    """
    One row from a CSV that was NOT added as a new contact.

    Statuses:
      invalid          — phone could not be normalised to 2567XXXXXXXX
      duplicate_db     — phone already belongs to a contact of this org
      duplicate_file   — same phone appeared earlier in the same file
      opted_out        — phone is on the platform-wide opt-out list
    """
    __tablename__ = 'contact_import_issue'
    id = db.Column(db.Integer, primary_key=True)
    import_id = db.Column(
        db.Integer,
        db.ForeignKey('contact_import.id',
                      name='fk_contact_import_issue_import'),
        nullable=False, index=True)

    row_num = db.Column(db.Integer)
    status = db.Column(db.String(20), nullable=False, index=True)
    reason = db.Column(db.String(255))
    raw_phone = db.Column(db.String(60))
    canonical = db.Column(db.String(20))

    # What the file said for this row. Preserved so the error CSV can be
    # re-imported after the user fixes the phone number.
    name = db.Column(db.String(120))
    group_name = db.Column(db.String(80))
    district_name = db.Column(db.String(80))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_contact_import_issue_import_status',
                 'import_id', 'status'),
    )