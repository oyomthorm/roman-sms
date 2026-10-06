"""
Shared pytest fixtures.

Every test gets a fresh in-memory SQLite database. Uses StaticPool so all
connections in a test share the same in-memory database — without it,
SQLAlchemy opens a new empty database per connection and everything
appears missing.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.pool import StaticPool

from app import create_app
from app.extensions import db as _db
from app.models import (Organization, User, Plan, Subscription,
                        Contact, Group, MessageTemplate, Campaign,
                        MessageLog, WalletTransaction, SendQueue,
                        OptOut, AuditLog)
from app.services import wallet as wallet_svc


class TestConfig:
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret'

    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False},
        'poolclass': StaticPool,
    }

    EGOSMS_API_MODE = 'json'
    EGOSMS_USERNAME = 'test-user'
    EGOSMS_PASSWORD = 'test-pass'
    EGOSMS_DEFAULT_SENDER = 'ROMANSMS'
    EGOSMS_TIMEOUT = 5

    WORKER_POLL_SECONDS = 1
    WORKER_BATCH_SIZE = 50
    WORKER_SEND_INTERVAL = 0.0

    MAX_BRAND_PREFIX_CHARS = 20
    SMS_SEGMENT_CHARS = 160


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def session(db):
    """Alias for db.session, for tests that want a shorter name."""
    return db.session


# --------------------------------------------------------------------------
# Organizations
# --------------------------------------------------------------------------

@pytest.fixture
def master_org(db):
    org = Organization(
        name='Roman SMS', slug='roman-sms', brand_name='Roman SMS',
        status='active', is_master=True,
    )
    db.session.add(org)
    db.session.flush()

    # Fund the master reserve. Mirrors a Pahappa top-up at seed
    # time. Every internal credit in the app debits this wallet,
    # so tests that trigger grants need it non-empty.
    wallet_svc.credit(org.id, 100_000, reason='master_opening_balance')

    db.session.commit()
    return org


@pytest.fixture
def associate_org(db, master_org):
    org = Organization(
        name='Kampalafit', slug='kampalafit', brand_name='Kampalafit',
        status='active', is_master=False, parent_id=master_org.id,
    )
    db.session.add(org)
    db.session.commit()
    return org


@pytest.fixture
def second_org(db, master_org):
    org = Organization(
        name='Ntinda Pharmacy', slug='ntinda', brand_name='Ntinda',
        status='active', is_master=False, parent_id=master_org.id,
    )
    db.session.add(org)
    db.session.commit()
    return org


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------

@pytest.fixture
def master_admin(db, master_org):
    u = User(email='master@test.local', full_name='Master',
             role='master_admin', org_id=master_org.id)
    u.set_password('masterpass')
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def associate_admin(db, associate_org):
    u = User(email='admin@kampalafit.test', full_name='Kampa Admin',
             role='associate_admin', org_id=associate_org.id)
    u.set_password('assocpass')
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def second_admin(db, second_org):
    u = User(email='admin@ntinda.test', full_name='Ntinda Admin',
             role='associate_admin', org_id=second_org.id)
    u.set_password('ntindapass')
    db.session.add(u)
    db.session.commit()
    return u


# --------------------------------------------------------------------------
# Plans and subscriptions
# --------------------------------------------------------------------------

@pytest.fixture
def plan(db):
    p = Plan(name='Starter', price=50000, credits=1000,
             validity_days=30, max_contacts=10000,
             max_per_minute=30, max_per_day=2000)
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture
def active_subscription(db, associate_org, plan):
    s = Subscription(
        org_id=associate_org.id, plan_id=plan.id,
        starts_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        status='active', credits_granted=plan.credits,
    )
    db.session.add(s)
    db.session.commit()
    return s


@pytest.fixture
def subscribed_associate(db, associate_org, master_org, plan):
    """Associate with an active subscription and a funded wallet."""
    sub = Subscription(
        org_id=associate_org.id, plan_id=plan.id,
        starts_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        status='active', credits_granted=plan.credits,
    )
    db.session.add(sub)

    # Transfer from the master reserve. `master_org` funds itself in
    # its own fixture, so this never runs short.
    wallet_svc.transfer(
        master_org.id, associate_org.id, 500,
        reason='plan_grant',
    )
    db.session.commit()
    return associate_org


# --------------------------------------------------------------------------
# Login helpers
# --------------------------------------------------------------------------

def login(client, email, password):
    return client.post('/login',
                       data={'email': email, 'password': password},
                       follow_redirects=True)


@pytest.fixture
def as_master(client, master_admin):
    login(client, master_admin.email, 'masterpass')
    return client


@pytest.fixture
def as_associate(client, associate_admin):
    login(client, associate_admin.email, 'assocpass')
    return client