from app.extensions import db


class District(db.Model):
    __tablename__ = 'district'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, index=True)
    region = db.Column(db.String(20), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint('name', name='uq_district_name'),
    )

    def __repr__(self):
        return f'<District {self.name} ({self.region})>'