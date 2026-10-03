"""
Application configuration.

Reads from environment variables (loaded from .env by python-dotenv).
Postgres is required in production. Local development points
DATABASE_URL at the docker-compose.yml Postgres instance.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _require(name):
    """Fetch a required environment variable, failing loudly if missing."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f'{name} is required. Set it in .env or the environment.\n'
            f'Example: DATABASE_URL=postgresql://roman:roman@localhost:5432/romansms'
        )
    return value


class Config:
    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-not-safe-change-me')

    # Postgres is the only supported production backend. The wallet relies
    # on SELECT ... FOR UPDATE, which SQLite silently ignores.
    SQLALCHEMY_DATABASE_URI = _require('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_size': 10,
        'max_overflow': 20,
        'pool_recycle': 3600,
    }

    # ------------------------------------------------------------------
    # Pahappa / EgoSMS
    # ------------------------------------------------------------------
    EGOSMS_API_MODE = os.environ.get('EGOSMS_API_MODE', 'json')
    EGOSMS_USERNAME = os.environ.get('EGOSMS_USERNAME', '')
    EGOSMS_PASSWORD = os.environ.get('EGOSMS_PASSWORD', '')
    EGOSMS_DEFAULT_SENDER = os.environ.get('EGOSMS_DEFAULT_SENDER', 'ROMANSMS')
    EGOSMS_TIMEOUT = int(os.environ.get('EGOSMS_TIMEOUT', 20))
    EGOSMS_SANDBOX = os.environ.get('EGOSMS_SANDBOX', '0') == '1'
    EGOSMS_BATCH_MAX = int(os.environ.get('EGOSMS_BATCH_MAX', 1000))

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------
    WORKER_POLL_SECONDS = int(os.environ.get('WORKER_POLL_SECONDS', 5))
    WORKER_BATCH_SIZE = int(os.environ.get('WORKER_BATCH_SIZE', 200))
    WORKER_SEND_INTERVAL = float(os.environ.get('WORKER_SEND_INTERVAL', 0.3))

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------
    MAX_BRAND_PREFIX_CHARS = 20
    SMS_SEGMENT_CHARS = 160

    # ------------------------------------------------------------------
    # Public URL (opt-out links, password reset links)
    # ------------------------------------------------------------------
    PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '')

    # ------------------------------------------------------------------
    # Webhook for delivery reports from Pahappa
    # ------------------------------------------------------------------
    WEBHOOK_TOKEN = os.environ.get('WEBHOOK_TOKEN', '')

    # ------------------------------------------------------------------
    # Payment instructions shown on unpaid invoices
    # ------------------------------------------------------------------
    PAYMENT_INSTRUCTIONS = os.environ.get(
        'PAYMENT_INSTRUCTIONS',
        'Pay via MTN MoMo to 0772 123456 or bank transfer to '
        'Stanbic 1234567890 (Roman SMS Ltd). '
        'Use your invoice number as the payment reference.',
    )

    # ------------------------------------------------------------------
    # Mailer
    # ------------------------------------------------------------------
    MAIL_BACKEND = os.environ.get('MAIL_BACKEND', 'console')  # console | smtp
    MAIL_HOST = os.environ.get('MAIL_HOST', '')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', '1') == '1'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_FROM = os.environ.get('MAIL_FROM', 'no-reply@romansms.local')

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------
    ALERT_EMAIL = os.environ.get('ALERT_EMAIL', '')

    # ------------------------------------------------------------------
    # Backups
    # ------------------------------------------------------------------
    BACKUP_DIR = os.environ.get('BACKUP_DIR', 'backups')
    BACKUP_KEEP = int(os.environ.get('BACKUP_KEEP', 30))

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = os.environ.get('LOG_FORMAT', 'text')  # text | json

    # ------------------------------------------------------------------
    # Master seed (used only by scripts/seed.py on first run)
    # ------------------------------------------------------------------
    MASTER_EMAIL = os.environ.get('MASTER_EMAIL', 'admin@romansms.local')
    MASTER_PASSWORD = os.environ.get('MASTER_PASSWORD', 'ChangeMe123!')


    # Self-signup
    SIGNUP_ENABLED = os.environ.get('SIGNUP_ENABLED', '1') == '1'
    SIGNUP_STARTER_CREDITS = int(
        os.environ.get('SIGNUP_STARTER_CREDITS', 100))
    

    # Scheduler timezone offset in hours from UTC.
    # Uganda is UTC+3 year-round, no DST.
    SCHEDULER_TZ_OFFSET_HOURS = int(
        os.environ.get('SCHEDULER_TZ_OFFSET_HOURS', 3))
    
    
class TestConfig(Config):
    """
    Used by the test suite. Overrides the DATABASE_URL requirement with
    SQLite in-memory (StaticPool so all connections share one DB).

    Tests do not exercise concurrency, so the wallet's FOR UPDATE lock is
    irrelevant here. The concurrency guarantee is verified separately by
    scripts/test_wallet_concurrency.py against a real Postgres.
    """
    TESTING = True
    SECRET_KEY = 'test-secret'
    WTF_CSRF_ENABLED = False

    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SQLALCHEMY_ENGINE_OPTIONS = {}

    EGOSMS_SANDBOX = True
    WORKER_SEND_INTERVAL = 0.0
    WORKER_BATCH_SIZE = 50
    PUBLIC_BASE_URL = ''
    WEBHOOK_TOKEN = 'test-webhook-token'