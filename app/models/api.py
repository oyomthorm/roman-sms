import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, JSON, UniqueConstraint
from app.extensions import db

TOKEN_PREFIX = "rsms_"

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

class ApiToken(db.Model):
    __tablename__ = "api_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    device_label = Column(String(120), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > datetime.now(timezone.utc)

def issue_token(user, device_label: str = "") -> str:
    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    row = ApiToken(
        user_id=user.id,
        token_hash=_hash(raw),
        device_label=device_label,
        expires_at=datetime.now(timezone.utc) + timedelta(days=90)
    )
    db.session.add(row)
    db.session.flush()
    return raw

def authenticate(raw: str):
    if not raw or not raw.startswith(TOKEN_PREFIX):
        return None
    row = ApiToken.query.filter_by(token_hash=_hash(raw)).first()
    if row is None or not row.is_active():
        return None
    # Touch token to extend expiry
    now = datetime.now(timezone.utc)
    if row.last_used_at is None or (now - row.last_used_at) > timedelta(hours=6):
        row.last_used_at = now
        row.expires_at = now + timedelta(days=90)
        db.session.commit()
    return row.user_id

class ApiIdempotency(db.Model):
    __tablename__ = "api_idempotency"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(80), nullable=False)
    response_status = Column(Integer, nullable=True)
    response_body = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_api_idempotency_user_key"),)
