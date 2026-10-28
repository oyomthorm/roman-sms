from flask import Blueprint
from .auth import bp as auth_bp
from .wallet import bp as wallet_bp
from .campaigns import bp as campaigns_bp
from .contacts import bp as contacts_bp
from .plans import bp as plans_bp
from .chat import bp as chat_bp
from .notifications import bp as notif_bp

api_v1_bp = Blueprint("api_v1", __name__)
api_v1_bp.register_blueprint(auth_bp)
api_v1_bp.register_blueprint(wallet_bp)
api_v1_bp.register_blueprint(campaigns_bp)
api_v1_bp.register_blueprint(contacts_bp)
api_v1_bp.register_blueprint(plans_bp)
api_v1_bp.register_blueprint(chat_bp)
api_v1_bp.register_blueprint(notif_bp)
