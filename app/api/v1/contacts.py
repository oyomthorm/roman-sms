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
