"""
Chat service.

Two channel kinds:
  dm         — between the master org and one associate org
  broadcast  — one global channel, all authenticated users

No websockets, no Redis. Polling against a simple JSON endpoint. The
client polls for messages newer than the last id it has seen.
"""
from datetime import datetime

from sqlalchemy import func, or_

from app.extensions import db
from app.models import (ChatChannel, ChatMessage, ChatReadState,
                        Organization, User)
from app.services.audit import log as audit


BROADCAST_NAME = 'Platform'
BROADCAST_DESCRIPTION = 'Announcements and questions from all associates.'


class ChatError(Exception):
    pass


# --------------------------------------------------------------------------
# Channel access
# --------------------------------------------------------------------------

def get_broadcast_channel():
    ch = ChatChannel.query.filter_by(kind='broadcast').first()
    if ch:
        return ch
    ch = ChatChannel(
        kind='broadcast',
        name=BROADCAST_NAME,
        description=BROADCAST_DESCRIPTION,
    )
    db.session.add(ch)
    db.session.commit()
    return ch


def get_or_create_dm(associate_org):
    """One DM per associate org, always paired with the master."""
    if associate_org is None or associate_org.is_master:
        raise ChatError('DMs exist between the master and an associate.')

    ch = (ChatChannel.query
          .filter_by(kind='dm', associate_org_id=associate_org.id)
          .first())
    if ch:
        return ch
    ch = ChatChannel(kind='dm', associate_org_id=associate_org.id)
    db.session.add(ch)
    db.session.commit()
    return ch


def can_access(user, channel):
    if user.is_master:
        return True
    if channel.kind == 'broadcast':
        return True
    if channel.kind == 'dm' and channel.associate_org_id == user.org_id:
        return True
    return False


def get_channel_for_user(user, channel_id):
    ch = db.session.get(ChatChannel, channel_id)
    if not ch or not can_access(user, ch):
        return None
    return ch


# --------------------------------------------------------------------------
# Listing
# --------------------------------------------------------------------------

def list_channels_for_user(user):
    """
    Return a list of dicts:
      {channel, label, sublabel, unread, last_message_at}
    Ordered: broadcast first, then DMs by most recent activity.
    """
    items = []

    # Broadcast
    b = get_broadcast_channel()
    items.append(_channel_summary(user, b,
                                  label=BROADCAST_NAME,
                                  sublabel=BROADCAST_DESCRIPTION))

    if user.is_master:
        # DM for every associate, created lazily so unread counts work.
        associates = (Organization.query
                      .filter_by(is_master=False)
                      .order_by(Organization.name)
                      .all())
        dms = []
        for assoc in associates:
            dm = get_or_create_dm(assoc)
            dms.append(_channel_summary(user, dm,
                                        label=assoc.name,
                                        sublabel=f'{assoc.prefix.strip()}'))
        dms.sort(key=lambda x: x['last_message_at'] or datetime.min,
                 reverse=True)
        items.extend(dms)
    else:
        dm = get_or_create_dm(user.organization)
        items.append(_channel_summary(user, dm,
                                      label='Roman SMS support',
                                      sublabel='Direct line to the platform team'))

    return items


def _channel_summary(user, channel, label, sublabel):
    last = (ChatMessage.query
            .filter_by(channel_id=channel.id)
            .order_by(ChatMessage.id.desc())
            .first())
    return {
        'channel': channel,
        'label': label,
        'sublabel': sublabel,
        'unread': unread_count(user, channel),
        'last_message_at': last.created_at if last else channel.last_message_at,
        'last_snippet': (last.body[:60] + '…') if last and len(last.body) > 60
                        else (last.body if last else None),
        'last_author': last.author.full_name or last.author.email.split('@')[0]
                       if last else None,
    }


# --------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------

def send_message(channel, user, body):
    if not can_access(user, channel):
        raise ChatError('You cannot post in this channel.')

    body = (body or '').strip()
    if not body:
        raise ChatError('Message cannot be empty.')
    if len(body) > 4000:
        raise ChatError('Message is too long (4000 chars max).')

    msg = ChatMessage(channel_id=channel.id, author_id=user.id, body=body)
    db.session.add(msg)
    channel.last_message_at = datetime.utcnow()
    db.session.commit()

    # Sender is automatically caught up.
    mark_read(user, channel, commit=False)
    db.session.commit()
    return msg


def messages(channel, *, limit=200, after_id=None):
    q = ChatMessage.query.filter_by(channel_id=channel.id)
    if after_id:
        q = q.filter(ChatMessage.id > after_id)
    q = q.order_by(ChatMessage.id.asc() if after_id else ChatMessage.id.desc())
    rows = q.limit(limit).all()
    if not after_id:
        rows.reverse()
    return rows


# --------------------------------------------------------------------------
# Read state
# --------------------------------------------------------------------------

def mark_read(user, channel, commit=True):
    state = (ChatReadState.query
             .filter_by(user_id=user.id, channel_id=channel.id)
             .first())
    if not state:
        state = ChatReadState(user_id=user.id, channel_id=channel.id)
        db.session.add(state)
    state.last_read_at = datetime.utcnow()
    if commit:
        db.session.commit()
    return state


def unread_count(user, channel):
    state = (ChatReadState.query
             .filter_by(user_id=user.id, channel_id=channel.id)
             .first())
    q = ChatMessage.query.filter_by(channel_id=channel.id)
    if state and state.last_read_at:
        q = q.filter(ChatMessage.created_at > state.last_read_at)
    # A user does not count their own messages as unread.
    q = q.filter(ChatMessage.author_id != user.id)
    return q.count()


def total_unread(user):
    """Unread across every channel the user can see. For the sidebar badge."""
    total = 0

    b = get_broadcast_channel()
    total += unread_count(user, b)

    if user.is_master:
        # Only count DMs that exist and have messages — do not create rows here.
        dms = (ChatChannel.query
               .filter_by(kind='dm')
               .all())
        for ch in dms:
            total += unread_count(user, ch)
    else:
        ch = (ChatChannel.query
              .filter_by(kind='dm', associate_org_id=user.org_id)
              .first())
        if ch:
            total += unread_count(user, ch)

    return total