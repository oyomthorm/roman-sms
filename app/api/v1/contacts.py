from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from app.models import Organization
from app.extensions import db
from app.api.v1 import serializers
from app.models import Contact
from app.services import contacts as contacts_svc

bp = Blueprint("api_contacts", __name__, url_prefix="/api/v1/contacts")

@bp.get("")
@login_required
def index():
    contacts = Contact.query.filter_by(org_id=current_user.org_id).order_by(Contact.id.desc()).limit(200).all()
    return jsonify(serializers.paginated([serializers.contact(c) for c in contacts], None))

@bp.post("")
@login_required
def create():
    data = request.get_json(silent=True) or {}
    try:
        c = contacts_svc.add_contact(
            org=Organization.query.get(current_user.org_id), phone=data.get("phone"), 
            name=data.get("name"), group_id=data.get("group_id")
        )
        db.session.commit()
        return jsonify(serializers.contact(c)), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "invalid_contact", "message": str(e)}), 422


@bp.patch("/<int:contact_id>")
@login_required
def patch(contact_id):
    c = Contact.query.filter_by(id=contact_id, org_id=current_user.org_id).first()
    if not c:
        return jsonify({"error": "not_found"}), 404

    data = request.get_json(silent=True) or {}
    kwargs = {}

    if "name" in data:
        kwargs["name"] = data["name"]

    if "group_id" in data:
        if data["group_id"] is None:
            kwargs["clear_group"] = True
        else:
            kwargs["group_id"] = data["group_id"]

    if "district_id" in data:
        if data["district_id"] is None:
            kwargs["clear_district"] = True
        else:
            kwargs["district_id"] = data["district_id"]

    if kwargs:
        try:
            c = contacts_svc.update_contact(
                Organization.query.get(current_user.org_id), contact_id, **kwargs
            )
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": "invalid_update", "message": str(e)}), 422

    return jsonify(serializers.contact(c)), 200

@bp.delete("/<int:contact_id>")
@login_required
def delete(contact_id):
    c = Contact.query.filter_by(id=contact_id, org_id=current_user.org_id).first()
    if not c:
        return jsonify({"error": "not_found"}), 404
    try:
        contacts_svc.delete_contact(
            Organization.query.get(current_user.org_id), contact_id
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "delete_failed", "message": str(e)}), 422
    return "", 204

@bp.post("/<int:contact_id>/optout")
@login_required
def optout(contact_id):
    c = Contact.query.filter_by(id=contact_id, org_id=current_user.org_id).first()
    if not c:
        return jsonify({"error": "not_found"}), 404
    try:
        c = contacts_svc.mark_opted_out(
            Organization.query.get(current_user.org_id), contact_id
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "optout_failed", "message": str(e)}), 422
    return jsonify(serializers.contact(c)), 200

@bp.get("/<int:contact_id>")
@login_required
def get(contact_id):
    c = Contact.query.filter_by(id=contact_id, org_id=current_user.org_id).first()
    if not c:
        return jsonify({"error": "not_found"}), 404
    return jsonify(serializers.contact(c)), 200
