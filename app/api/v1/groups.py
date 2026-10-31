from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required

from app.models import Organization
from app.api.v1 import serializers
from app.services import groups as svc

bp = Blueprint("api_groups", __name__, url_prefix="/api/v1/groups")


def _org():
    return Organization.query.get(current_user.org_id)


def _serialize_row(row):
    # svc.list_groups returns [(group, contact_count), ...]
    if isinstance(row, tuple):
        g, count = row
        return serializers.group(g, contact_count=count)
    return serializers.group(row)


@bp.get("")
@login_required
def index():
    rows = svc.list_groups(_org())
    return jsonify(serializers.paginated([_serialize_row(r) for r in rows], None))


@bp.post("")
@login_required
def create():
    data = request.get_json(silent=True) or {}
    try:
        g = svc.create(_org(),
                       name=data.get("name"),
                       description=data.get("description"),
                       actor_id=current_user.id)
    except svc.GroupError as e:
        # Service commits internally; do NOT rollback here.
        return jsonify({"error": "invalid_group", "message": str(e)}), 422
    return jsonify(serializers.group(g, contact_count=0)), 201


@bp.get("/<int:group_id>")
@login_required
def get(group_id):
    g = svc.get(_org(), group_id)
    if not g:
        return jsonify({"error": "not_found"}), 404
    return jsonify(serializers.group(g)), 200


@bp.patch("/<int:group_id>")
@login_required
def patch(group_id):
    data = request.get_json(silent=True) or {}
    if "name" not in data and "description" not in data:
        return jsonify({"error": "invalid_update",
                        "message": "Provide name and/or description."}), 422

    current = svc.get(_org(), group_id)
    if not current:
        return jsonify({"error": "not_found"}), 404

    name = data["name"] if "name" in data else current.name
    description = data["description"] if "description" in data else current.description
    try:
        g = svc.update(_org(), group_id,
                       name=name, description=description,
                       actor_id=current_user.id)
    except svc.GroupError as e:
        return jsonify({"error": "invalid_update", "message": str(e)}), 422
    return jsonify(serializers.group(g)), 200


@bp.delete("/<int:group_id>")
@login_required
def delete(group_id):
    current = svc.get(_org(), group_id)
    if not current:
        return jsonify({"error": "not_found"}), 404

    raw_move = request.args.get("move_to", "").strip()
    move_to_id = int(raw_move) if raw_move.isdigit() else None
    try:
        moved, target = svc.delete(_org(), group_id,
                                   move_to_group_id=move_to_id,
                                   actor_id=current_user.id)
    except svc.GroupError as e:
        return jsonify({"error": "delete_failed", "message": str(e)}), 422
    return jsonify({"ok": True,
                    "moved_count": moved,
                    "moved_to": target.id if target else None}), 200