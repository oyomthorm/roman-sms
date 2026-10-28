from flask import Blueprint, request, jsonify, abort
from flask_login import current_user, login_required
from app.extensions import db
from app.models import ChatChannel, ChatMessage, ChatReadState


bp = Blueprint("api_chat", __name__, url_prefix="/api/v1/chat")


def _channel_or_404(cid: int) -> ChatChannel:
    """Fetch a channel owned by the caller's org, or 404.

    Every channel-scoped read/write MUST go through this. Without it, any
    logged-in associate can read/post into another org's DM by iterating
    integer channel ids.
    """
    ch = ChatChannel.query.filter_by(
        id=cid, org_id=current_user.org_id,
    ).first()
    if ch is None:
        abort(404)
    return ch


@bp.get("/channels")
@login_required
def channels():
    # Scope strictly to this org. Cross-org broadcast is a separate
    # product decision (see MOBILE_API.md notes) and must NOT reuse this
    # per-org 'broadcast' row.
    channels = ChatChannel.query.filter(
        ChatChannel.org_id == current_user.org_id,
        ChatChannel.kind.in_(['dm', 'broadcast']),
    ).all()

    # Auto-create only when THIS org has none (not when the global table
    # is empty, which is what caused duplicate rows across orgs).
    if not channels:
        master_ch = ChatChannel(name="Roman SMS Support", kind="dm", org_id=current_user.org_id)
        broadcast_ch = ChatChannel(name="Platform Announcements", kind="broadcast", org_id=current_user.org_id)
        db.session.add_all([master_ch, broadcast_ch])
        db.session.commit()
        channels = [master_ch, broadcast_ch]

    result = []
    for ch in channels:
        # Check unread count
        read_state = ChatReadState.query.filter_by(channel_id=ch.id, user_id=current_user.id).first()
        last_read_id = read_state.last_read_message_id if read_state else 0
        
        unread = ChatMessage.query.filter(
            ChatMessage.channel_id == ch.id,
            ChatMessage.id > last_read_id,
            ChatMessage.sender_id != current_user.id
        ).count()

        result.append({
            "id": ch.id, "name": ch.name, "kind": ch.kind, "unread": unread
        })
    return jsonify({"items": result})

@bp.get("/channels/<int:cid>/messages")
@login_required
def messages(cid):
    _channel_or_404(cid)
    # Mark as read
    read_state = ChatReadState.query.filter_by(channel_id=cid, user_id=current_user.id).first()
    if not read_state:
        read_state = ChatReadState(channel_id=cid, user_id=current_user.id, last_read_message_id=0)
        db.session.add(read_state)
    
    msgs = ChatMessage.query.filter_by(channel_id=cid).order_by(ChatMessage.id.asc()).limit(100).all()
    if msgs:
        read_state.last_read_message_id = msgs[-1].id
        db.session.commit()

    return jsonify({"items": [{
        "id": m.id, "sender_id": m.sender_id, "sender_name": "Support" if m.sender_id != current_user.id else "You",
        "body": m.body, "created_at": m.created_at.isoformat()
    } for m in msgs]})

@bp.post("/channels/<int:cid>/messages")
@login_required
def send_message(cid):
    _channel_or_404(cid)
    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "empty_body", "message": "Message body is required."}), 422
    if len(body) > 4000:
        return jsonify({"error": "body_too_long", "message": "Message exceeds 4000 characters."}), 422
    msg = ChatMessage(channel_id=cid, sender_id=current_user.id, body=body)
    db.session.add(msg)
    db.session.commit()
    return jsonify({"id": msg.id, "created_at": msg.created_at.isoformat()}), 201
