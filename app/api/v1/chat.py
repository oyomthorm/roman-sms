from datetime import datetime
from flask import Blueprint, request, jsonify, abort
from flask_login import current_user, login_required
from sqlalchemy import or_, and_
from app.extensions import db
from app.models import ChatChannel, ChatMessage, ChatReadState

bp = Blueprint("api_chat", __name__, url_prefix="/api/v1/chat")


def _visible_channels_query():
    """Channels visible to current_user, scoped correctly.

    - dm        : only this user's org (associate_org_id == current_user.org_id)
    - broadcast : platform-wide (associate_org_id IS NULL) OR this org
    - master    : everything (safety valve; mobile should reject master login)
    """
    if getattr(current_user, "role", None) == "master_admin":
        return ChatChannel.query
    return ChatChannel.query.filter(
        or_(
            and_(ChatChannel.kind == "dm",
                 ChatChannel.associate_org_id == current_user.org_id),
            and_(ChatChannel.kind == "broadcast",
                 or_(ChatChannel.associate_org_id.is_(None),
                     ChatChannel.associate_org_id == current_user.org_id)),
        )
    )


def _channel_visible_or_404(cid):
    """Fetch a channel the caller is allowed to see, or 404.

    Every channel-scoped read/write MUST go through this. Without it, any
    logged-in associate can read or post into another org's DM by
    iterating integer channel ids.
    """
    ch = _visible_channels_query().filter(ChatChannel.id == cid).first()
    if ch is None:
        abort(404)
    return ch


def _ensure_default_channels():
    """Create this org's dm + per-org broadcast rows if missing.

    Does NOT create or modify the platform-wide broadcast row
    (associate_org_id IS NULL). That row is managed by the master console.
    """
    org_id = current_user.org_id
    existing = {
        ch.kind: ch for ch in ChatChannel.query.filter_by(
            associate_org_id=org_id,
        ).all()
    }
    created = False
    if "dm" not in existing:
        existing["dm"] = ChatChannel(
            name="Roman SMS Support", kind="dm", associate_org_id=org_id,
        )
        db.session.add(existing["dm"])
        created = True
    if "broadcast" not in existing:
        existing["broadcast"] = ChatChannel(
            name="Platform Announcements", kind="broadcast",
            associate_org_id=org_id,
        )
        db.session.add(existing["broadcast"])
        created = True
    if created:
        db.session.commit()


@bp.get("/channels")
@login_required
def channels():
    _ensure_default_channels()

    result = []
    for ch in _visible_channels_query().order_by(ChatChannel.id.asc()).all():
        read_state = ChatReadState.query.filter_by(
            channel_id=ch.id, user_id=current_user.id,
        ).first()
        last_read_at = read_state.last_read_at if read_state else None

        q = ChatMessage.query.filter(ChatMessage.channel_id == ch.id)
        if last_read_at is not None:
            q = q.filter(ChatMessage.created_at > last_read_at)
        q = q.filter(ChatMessage.author_id != current_user.id)
        unread = q.count()

        result.append({
            "id": ch.id,
            "name": ch.name,
            "kind": ch.kind,
            "unread": unread,
        })
    return jsonify({"items": result})


@bp.get("/channels/<int:cid>/messages")
@login_required
def messages(cid):
    ch = _channel_visible_or_404(cid)

    read_state = ChatReadState.query.filter_by(
        channel_id=ch.id, user_id=current_user.id,
    ).first()

    msgs = (
        ChatMessage.query
        .filter_by(channel_id=ch.id)
        .order_by(ChatMessage.id.asc())
        .limit(100)
        .all()
    )

    if msgs:
        now = datetime.utcnow()
        if read_state is None:
            read_state = ChatReadState(
                channel_id=ch.id, user_id=current_user.id, last_read_at=now,
            )
            db.session.add(read_state)
        else:
            read_state.last_read_at = now
        db.session.commit()

    return jsonify({"items": [{
        "id": m.id,
        "author_id": m.author_id,
        "body": m.body,
        "created_at": m.created_at.isoformat(),
    } for m in msgs]})


@bp.post("/channels/<int:cid>/messages")
@login_required
def send_message(cid):
    ch = _channel_visible_or_404(cid)

    # Platform-wide broadcast (associate_org_id IS NULL) is master -> all.
    # Associates may read it but must not post into the shared firehose.
    if ch.kind == "broadcast" and ch.associate_org_id is None:
        if getattr(current_user, "role", None) != "master_admin":
            return jsonify({
                "error": "read_only_channel",
                "message": "The platform broadcast channel is read-only.",
            }), 403

    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "empty_body",
                        "message": "Message body is required."}), 422
    if len(body) > 4000:
        return jsonify({"error": "body_too_long",
                        "message": "Message exceeds 4000 characters."}), 422

    msg = ChatMessage(
        channel_id=ch.id, author_id=current_user.id, body=body,
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({"id": msg.id,
                    "created_at": msg.created_at.isoformat()}), 201
