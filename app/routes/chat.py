from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify, abort)
from flask_login import login_required, current_user

from app.services import chat as svc

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/')
@login_required
def index():
    """Redirect to the most useful channel for this user."""
    if current_user.is_master:
        ch = svc.get_broadcast_channel()
    else:
        ch = svc.get_or_create_dm(current_user.organization)
    return redirect(url_for('chat.channel', cid=ch.id))


@chat_bp.route('/<int:cid>')
@login_required
def channel(cid):
    ch = svc.get_channel_for_user(current_user, cid)
    if not ch:
        abort(404)

    svc.mark_read(current_user, ch)

    msgs = svc.messages(ch, limit=200)
    channels = svc.list_channels_for_user(current_user)

    # Compute a display title for the active channel
    if ch.kind == 'broadcast':
        title = svc.BROADCAST_NAME
        subtitle = svc.BROADCAST_DESCRIPTION
    elif current_user.is_master:
        title = ch.associate_org.name
        subtitle = f'{ch.associate_org.prefix.strip()}'
    else:
        title = 'Roman SMS support'
        subtitle = 'Direct line to the platform team'

    return render_template(
        'chat/index.html',
        active=ch,
        channels=channels,
        messages=msgs,
        title=title,
        subtitle=subtitle,
        last_id=msgs[-1].id if msgs else 0,
    )


@chat_bp.route('/<int:cid>/send', methods=['POST'])
@login_required
def send(cid):
    ch = svc.get_channel_for_user(current_user, cid)
    if not ch:
        abort(404)

    try:
        svc.send_message(ch, current_user, request.form.get('body', ''))
    except svc.ChatError as e:
        flash(str(e), 'danger')

    return redirect(url_for('chat.channel', cid=ch.id))


@chat_bp.route('/<int:cid>/messages.json')
@login_required
def poll(cid):
    """
    Poll for messages newer than `since`. Used by the client every 3s.
    """
    ch = svc.get_channel_for_user(current_user, cid)
    if not ch:
        return jsonify({'error': 'not found'}), 404

    since = request.args.get('since', type=int) or 0
    rows = svc.messages(ch, after_id=since, limit=200)

    # Mark as read on each poll so unread badges stay accurate while
    # the user is looking at the channel.
    svc.mark_read(current_user, ch)

    return jsonify({
        'messages': [
            {
                'id': m.id,
                'body': m.body,
                'author_id': m.author_id,
                'author_name': (m.author.full_name
                                or m.author.email.split('@')[0]),
                'author_is_master': m.author.is_master,
                'author_initials': (m.author.full_name or m.author.email)[0].upper(),
                'created_at': m.created_at.isoformat(),
                'is_self': m.author_id == current_user.id,
            }
            for m in rows
        ]
    })