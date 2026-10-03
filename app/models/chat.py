from datetime import datetime
from app.extensions import db


class ChatChannel(db.Model):
    __tablename__ = 'chat_channel'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False, index=True)
    # 'dm'        — master ↔ one associate org
    # 'broadcast' — everyone (master + all associates)

    associate_org_id = db.Column(
        db.Integer, db.ForeignKey('organization.id',
                                  name='fk_chat_channel_associate_org'),
        nullable=True, index=True)
    name = db.Column(db.String(120))
    description = db.Column(db.String(255))

    last_message_at = db.Column(db.DateTime, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    associate_org = db.relationship('Organization')
    messages = db.relationship('ChatMessage', backref='channel',
                               lazy='dynamic',
                               cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('kind', 'associate_org_id',
                            name='uq_chat_channel_kind_org'),
    )


class ChatMessage(db.Model):
    __tablename__ = 'chat_message'
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(
        db.Integer,
        db.ForeignKey('chat_channel.id', name='fk_chat_message_channel'),
        nullable=False, index=True)
    author_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', name='fk_chat_message_author'),
        nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow,
                           index=True)

    author = db.relationship('User')

    __table_args__ = (
        db.Index('ix_chat_message_channel_created', 'channel_id',
                 'created_at'),
    )


class ChatReadState(db.Model):
    __tablename__ = 'chat_read_state'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', name='fk_chat_read_user'),
        nullable=False, index=True)
    channel_id = db.Column(
        db.Integer,
        db.ForeignKey('chat_channel.id', name='fk_chat_read_channel'),
        nullable=False, index=True)
    last_read_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'channel_id',
                            name='uq_chat_read_user_channel'),
    )