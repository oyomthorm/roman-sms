from flask import Blueprint

from app.extensions import csrf

from .dashboard import bp as dashboard_bp
from .auth import bp as auth_bp
from .wallet import bp as wallet_bp
from .campaigns import bp as campaigns_bp
from .contacts import bp as contacts_bp
from .plans import bp as plans_bp
from .chat import bp as chat_bp
from .notifications import bp as notif_bp
from .contacts import bp as contacts_bp
from .groups import bp as groups_bp

# The mobile API authenticates with Bearer tokens (see install_api_auth in
# app/api/v1/utils.py); it does not use session cookies, so Flask-WTF's
# CSRF protection does not apply. Exempt each leaf blueprint here, before
# registering it on the parent blueprint, so that:
#   - the exemption uses only Flask-WTF's public csrf.exempt(blueprint) API
#   - adding a new child blueprint below automatically requires thinking
#     about whether it should also be exempted (it is added to this tuple)
#   - create_app() stays focused on wiring, not on per-blueprint CSRF rules
#
# HTML blueprints registered elsewhere in create_app() are NOT in this list
# and remain CSRF-protected.
api_v1_bp = Blueprint("api_v1", __name__)

_CHILDREN = (
    dashboard_bp,
    auth_bp,
    wallet_bp,
    campaigns_bp,
    contacts_bp,
    groups_bp,
    plans_bp,
    chat_bp,
    notif_bp,
)

for _child in _CHILDREN:
    csrf.exempt(_child)
    api_v1_bp.register_blueprint(_child)
