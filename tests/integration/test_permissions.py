from tests.factories import ContactFactory, UserFactory, OrgFactory


def test_associate_cannot_read_other_org_contact(client, app, db,
                                                 associate_admin,
                                                 subscribed_associate):
    other = OrgFactory()
    other_contact = ContactFactory(org_id=other.id, phone='256700999999')

    client.post('/login', data={
        'email': associate_admin.email,
        'password': 'assocpass',
    }, follow_redirects=True)

    resp = client.get(f'/contacts/{other_contact.id}/edit')
    # Should not see it
    assert resp.status_code == 404


def test_associate_cannot_read_master_routes(client, app, db, associate_admin):
    client.post('/login', data={
        'email': associate_admin.email,
        'password': 'assocpass',
    }, follow_redirects=True)
    resp = client.get('/master/')
    assert resp.status_code == 403


def test_master_can_read_master_route(client, app, db, master_admin):
    client.post('/login', data={
        'email': master_admin.email,
        'password': 'masterpass',
    }, follow_redirects=True)
    resp = client.get('/master/')
    assert resp.status_code == 200


def test_logout_requires_login(client):
    resp = client.get('/campaigns/', follow_redirects=False)
    assert resp.status_code == 302