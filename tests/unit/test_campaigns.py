import pytest
from app.models import OptOut, WalletTransaction
from app.services import wallet as wallet_svc
from app.services import campaigns as svc
from tests.factories import ContactFactory, UserFactory


def test_campaign_debits_and_creates_logs(app, db, subscribed_associate):
    org = subscribed_associate
    user = UserFactory(org=org)
    for _ in range(3):
        ContactFactory(org_id=org.id)

    starting_balance = wallet_svc.get_balance(org.id)
    campaign, segs = svc.create_campaign(
        org, name='Test', body='Hello {{name}}', created_by=user.id)

    assert campaign.total == 3
    assert segs == 3
    assert campaign.status == 'queued'
    assert wallet_svc.get_balance(org.id) == starting_balance - 3

    from app.models import MessageLog
    logs = MessageLog.query.filter_by(campaign_id=campaign.id).all()
    assert len(logs) == 3
    assert all(m.body.startswith('Kampalafit: ') for m in logs)


def test_campaign_excludes_opted_out_contacts(app, db, subscribed_associate):
    org = subscribed_associate
    user = UserFactory(org=org)
    ContactFactory(org_id=org.id, phone='256700000001', opted_out=True)
    ContactFactory(org_id=org.id, phone='256700000002')

    campaign, _ = svc.create_campaign(
        org, name='Test', body='Hello', created_by=user.id)
    assert campaign.total == 1


def test_campaign_excludes_platform_optouts(app, db, subscribed_associate):
    org = subscribed_associate
    user = UserFactory(org=org)
    c = ContactFactory(org_id=org.id, phone='256700000003')
    db.session.add(OptOut(phone=c.phone, reason='test'))
    db.session.commit()

    with pytest.raises(svc.CampaignError, match='No eligible'):
        svc.create_campaign(org, name='Test', body='Hello',
                            created_by=user.id)


def test_campaign_refuses_insufficient_credits(app, db, subscribed_associate):
    org = subscribed_associate
    user = UserFactory(org=org)
    for _ in range(500):
        ContactFactory(org_id=org.id)
    # Drain the wallet
    balance = wallet_svc.get_balance(org.id)
    wallet_svc.debit(org.id, balance, reason='adjustment')
    db.session.commit()

    with pytest.raises(svc.CampaignError, match='Insufficient'):
        svc.create_campaign(org, name='Test', body='Hello',
                            created_by=user.id)


def test_campaign_ledger_invariant(app, db, subscribed_associate):
    org = subscribed_associate
    user = UserFactory(org=org)
    ContactFactory(org_id=org.id)
    svc.create_campaign(org, name='Test', body='Hello', created_by=user.id)

    total = db.session.query(db.func.sum(WalletTransaction.delta)) \
        .filter_by(org_id=org.id).scalar()
    last = (WalletTransaction.query.filter_by(org_id=org.id)
            .order_by(WalletTransaction.id.desc()).first())
    assert total == last.balance_after == wallet_svc.get_balance(org.id)


def test_campaign_error_leaves_no_rows_on_insufficient(app, db, subscribed_associate):
    org = subscribed_associate
    user = UserFactory(org=org)
    ContactFactory(org_id=org.id)
    balance = wallet_svc.get_balance(org.id)
    wallet_svc.debit(org.id, balance, reason='adjustment')
    db.session.commit()

    from app.models import Campaign
    before = Campaign.query.filter_by(org_id=org.id).count()
    with pytest.raises(svc.CampaignError):
        svc.create_campaign(org, name='Test', body='Hello',
                            created_by=user.id)
    after = Campaign.query.filter_by(org_id=org.id).count()
    assert after == before