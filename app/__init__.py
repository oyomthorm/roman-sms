import os

from flask import Flask
from config import Config
from .extensions import db, login_manager, csrf, migrate, limiter
from .errors import register_error_handlers
from .logging_config import configure_logging


def _normalize_db_url(url: str) -> str:
    """
    Ensure the DATABASE_URL uses the psycopg (v3) driver.

    Render and Heroku hand out URLs like ``postgres://...`` or
    ``postgresql://...`` which SQLAlchemy maps to the psycopg2 dialect
    by default. We use psycopg v3, so force ``postgresql+psycopg://``.
    """
    if not url:
        return url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql+postgresql://"):
        url = url.replace("postgresql+postgresql://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    # ------------------------------------------------------------------
    # Database URL + engine options
    # ------------------------------------------------------------------
    # 1) Normalise the driver scheme so Render's `postgresql://...`
    #    is turned into `postgresql+psycopg://...` automatically.
    raw_db_url = app.config.get("SQLALCHEMY_DATABASE_URI") or os.environ.get("DATABASE_URL")
    if raw_db_url:
        app.config["SQLALCHEMY_DATABASE_URI"] = _normalize_db_url(raw_db_url)

    # 2) Pool settings that survive Render's idle-connection reaper.
    #    - pool_pre_ping: issues SELECT 1 before reusing a pooled conn.
    #    - pool_recycle:  recycles connections older than 5 minutes.
    app.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS", {})
    app.config["SQLALCHEMY_ENGINE_OPTIONS"].update({
        "pool_pre_ping": True,
        "pool_recycle": 300,
    })

    # ------------------------------------------------------------------
    # Extensions
    # ------------------------------------------------------------------
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
        from flask import g, has_request_context
        from flask_login import current_user
        from app.services import notifications
        from app.services import chat as chat_svc

        # Background jobs (worker, cron) have no request context and no
        # current_user. Return empty defaults so any template render they
        # trigger does not crash.
        if not has_request_context() or not current_user.is_authenticated:
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

        All None for anonymous users, the master admin, and background jobs.
        """
        from flask import g, has_request_context
        from flask_login import current_user
        from app.services.wallet import get_balance
        from app.services.entitlements import current_rate_ugx

        if (not has_request_context()
                or not current_user.is_authenticated
                or current_user.is_master):
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