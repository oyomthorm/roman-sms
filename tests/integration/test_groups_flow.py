from app.models import Group, Contact
from app.services import contacts as contacts_svc
from app.services import campaigns as campaigns_svc
from app.services import wallet as wallet_svc
from tests.factories import UserFactory


def _login(client, user, password='assocpass'):
    client.post('/login', data={'email': user.email,
                                'password': password},
                follow_redirects=True)


def test_import_creates_groups_automatically(app, db,
                                              subscribed_associate):
    org = subscribed_associate
    csv_bytes = (
        b"phone,name,group\n"
        b"0700000001,Alice,VIP\n"
        b"0700000002,Bob,Newsletter\n"
        b"0700000003,Carol,VIP\n"
        b"0700000004,Dave,\n"
    )
    import io
    result = contacts_svc.import_csv(
        org, io.BytesIO(csv_bytes))

    assert result.added == 4
    assert result.groups_created == 2

    names = {g.name for g in Group.query.filter_by(org_id=org.id).all()}
    assert names == {'VIP', 'Newsletter'}

    vip = Group.query.filter_by(org_id=org.id, name='VIP').first()
    assert Contact.query.filter_by(group_id=vip.id).count() == 2

    # Dave with no group column value
    dave = Contact.query.filter_by(
        org_id=org.id, phone='256700000004').first()
    assert dave.group_id is None


def test_import_reuses_existing_groups(app, db, subscribed_associate):
    org = subscribed_associate
    from app.services import groups as groups_svc
    groups_svc.create(org, name='VIP')

    import io
    csv_bytes = b"phone,name,group\n0700000010,Alice,VIP\n"
    result = contacts_svc.import_csv(org, io.BytesIO(csv_bytes))

    assert result.added == 1
    assert result.groups_created == 0
    assert Group.query.filter_by(org_id=org.id, name='VIP').count() == 1


def test_campaign_sends_to_group_only(app, db, subscribed_associate):
    org = subscribed_associate
    user = UserFactory(org=org)

    from app.services import groups as groups_svc
    vip = groups_svc.create(org, name='VIP')
    other = groups_svc.create(org, name='Other')

    for phone in ['256700001001', '256700001002']:
        db.session.add(Contact(org_id=org.id, phone=phone,
                               group_id=vip.id))
    db.session.add(Contact(org_id=org.id, phone='256700001003',
                           group_id=other.id))
    db.session.commit()

    contacts, segs = campaigns_svc.estimate(
        org, 'Hi', group_id=vip.id)
    assert contacts == 2

    starting = wallet_svc.get_balance(org.id)
    campaign, total_segs = campaigns_svc.create_campaign(
        org, name='VIP blast', body='Hi',
        group_id=vip.id, group_name='VIP',
        created_by=user.id)

    assert campaign.total == 2
    assert campaign.group_filter == 'VIP'
    assert wallet_svc.get_balance(org.id) == starting - 2


def test_delete_reassign_via_route(client, app, db,
                                   associate_admin, subscribed_associate):
    org = subscribed_associate
    from app.services import groups as groups_svc
    src = groups_svc.create(org, name='Source')
    dst = groups_svc.create(org, name='Dest')
    db.session.add(Contact(org_id=org.id, phone='256700002001',
                           group_id=src.id))
    db.session.commit()

    _login(client, associate_admin)
    resp = client.post(f'/groups/{src.id}/delete',
                       data={'move_to': str(dst.id)},
                       follow_redirects=True)
    assert resp.status_code == 200

    db.session.expire_all()
    assert Group.query.filter_by(id=src.id).first() is None
    contact = Contact.query.filter_by(phone='256700002001').first()
    assert contact.group_id == dst.id