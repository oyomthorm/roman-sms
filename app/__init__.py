from flask import Flask
from config import Config
from .extensions import db, login_manager, csrf, migrate, limiter
from .errors import register_error_handlers
from .logging_config import configure_logging


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)

    configure_logging(app)

    from .models import User

    @login_manager.user_loader
    def load_user(uid):
        u = db.session.get(User, int(uid))
        return u if u and u.is_active_flag else None

    @app.context_processor
    def _inject_notifications():
        from flask import g
        from flask_login import current_user
        from app.services import notifications
        from app.services import chat as chat_svc

        if not current_user.is_authenticated:
            return {
                'notifications': [],
                'unread_count': 0,
                'chat_unread_count': 0,
            }

        if not hasattr(g, '_notifications'):
            g._notifications = notifications.for_user(current_user)

        if not hasattr(g, '_chat_unread'):
            g._chat_unread = chat_svc.total_unread(current_user)

        return {
            'notifications': g._notifications,
            'unread_count': len(g._notifications),
            'chat_unread_count': g._chat_unread,
        }

    @app.context_processor
    def _inject_wallet():
        """
        Expose wallet balance, rate, and shilling value to every template.

        Returns:
          wallet_balance    — SMS credit count (integer)
          wallet_rate       — UGX per credit for the current org
          wallet_value_ugx  — shilling value of the balance

        All None for anonymous users and the master admin.
        """
        from flask import g
        from flask_login import current_user
        from app.services.wallet import get_balance
        from app.services.entitlements import current_rate_ugx

        if not current_user.is_authenticated or current_user.is_master:
            return {
                'wallet_balance': None,
                'wallet_rate': None,
                'wallet_value_ugx': None,
            }

        if not hasattr(g, '_wallet'):
            try:
                bal = get_balance(current_user.org_id)
                rate = current_rate_ugx(current_user.org_id)
                g._wallet = {
                    'wallet_balance': bal,
                    'wallet_rate': rate,
                    'wallet_value_ugx': bal * rate,
                }
            except Exception:
                g._wallet = {
                    'wallet_balance': None,
                    'wallet_rate': None,
                    'wallet_value_ugx': None,
                }

        return g._wallet

    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.contacts import contacts_bp
    from .routes.groups import groups_bp
    from .routes.templates import templates_bp
    from .routes.campaigns import campaigns_bp
    from .routes.reports import reports_bp
    from .routes.billing import billing_bp
    from .routes.master import master_bp
    from .routes.public import public_bp
    from .routes.landing import landing_bp
    from .routes.profile import profile_bp
    from .routes.chat import chat_bp
    from .routes.notifications import notifications_bp
    from .routes.settings import settings_bp
    from .routes.webhooks import webhooks_bp
    from .routes.signup import signup_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(landing_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(contacts_bp, url_prefix='/contacts')
    app.register_blueprint(groups_bp, url_prefix='/groups')
    app.register_blueprint(templates_bp, url_prefix='/templates')
    app.register_blueprint(campaigns_bp, url_prefix='/campaigns')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(billing_bp, url_prefix='/billing')
    app.register_blueprint(master_bp, url_prefix='/master')
    app.register_blueprint(profile_bp, url_prefix='/profile')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(notifications_bp, url_prefix='/notifications')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')
    app.register_blueprint(signup_bp, url_prefix='/signup')

    from .cli import register_cli
    register_cli(app)

    register_error_handlers(app)
    return app