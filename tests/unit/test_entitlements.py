import pytest
from datetime import datetime, timedelta
from app.models import Subscription
from app.services import wallet as wallet_svc
from app.services.entitlements import (check_can_send, check_contact_limit,
                                       EntitlementError)
from tests.factories import OrgFactory, ContactFactory


def test_no_subscription_blocks_send(app, db, associate_org):
    with pytest.raises(EntitlementError, match='No active plan'):
        check_can_send(associate_org, 1)


def test_suspended_org_blocks_send(app, db, associate_org, plan):
    associate_org.status = 'suspended'
    db.session.add(Subscription(
        org_id=associate_org.id, plan_id=plan.id,
        starts_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        status='active',
    ))
    db.session.commit()
    with pytest.raises(EntitlementError, match='suspended'):
        check_can_send(associate_org, 1)


def test_insufficient_credits_blocks_send(app, db, associate_org, plan):
    db.session.add(Subscription(
        org_id=associate_org.id, plan_id=plan.id,
        starts_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        status='active',
    ))
    wallet_svc.credit(associate_org.id, 5, reason='plan_grant')
    db.session.commit()
    with pytest.raises(EntitlementError, match='Insufficient'):
        check_can_send(associate_org, 10)


def test_sufficient_credits_passes(app, db, associate_org, plan):
    db.session.add(Subscription(
        org_id=associate_org.id, plan_id=plan.id,
        starts_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        status='active',
    ))
    wallet_svc.credit(associate_org.id, 100, reason='plan_grant')
    db.session.commit()
    sub = check_can_send(associate_org, 50)
    assert sub is not None


def test_contact_limit_blocks(app, db, associate_org, plan):
    plan.max_contacts = 2
    db.session.add(Subscription(
        org_id=associate_org.id, plan_id=plan.id,
        starts_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        status='active',
    ))
    ContactFactory(org_id=associate_org.id)
    ContactFactory(org_id=associate_org.id)
    db.session.commit()
    with pytest.raises(EntitlementError, match='Contact limit'):
        check_contact_limit(associate_org, 1)