from app.models import Invoice, Subscription
from app.services import wallet as wallet_svc


def _login(client, user, password):
    client.post('/login', data={'email': user.email, 'password': password},
                follow_redirects=True)


def test_associate_can_create_invoice_from_plans(client, app, db,
                                                 associate_admin, plan):
    _login(client, associate_admin, 'assocpass')
    resp = client.post(f'/billing/plans/{plan.id}/buy',
                       follow_redirects=True)
    assert resp.status_code == 200
    assert b'INV-' in resp.data

    inv = Invoice.query.filter_by(org_id=associate_admin.org_id).first()
    assert inv is not None
    assert inv.status == 'unpaid'


def test_master_can_mark_paid(client, app, db, master_admin,
                              associate_admin, plan):
    _login(client, associate_admin, 'assocpass')
    client.post(f'/billing/plans/{plan.id}/buy')
    inv = Invoice.query.filter_by(org_id=associate_admin.org_id).first()

    client.get('/logout')
    _login(client, master_admin, 'masterpass')

    starting = wallet_svc.get_balance(associate_admin.org_id)
    resp = client.post(
        f'/master/invoices/{inv.id}/mark-paid',
        data={
            'payment_method': 'momo',
            'payment_reference': 'MTN-ABC-123',
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    db.session.refresh(inv)
    assert inv.status == 'paid'
    assert inv.payment_reference == 'MTN-ABC-123'
    assert wallet_svc.get_balance(associate_admin.org_id) == \
        starting + plan.credits

    sub = Subscription.query.filter_by(
        org_id=associate_admin.org_id, status='active').first()
    assert sub is not None


def test_master_can_cancel_invoice(client, app, db, master_admin,
                                   associate_admin, plan):
    _login(client, associate_admin, 'assocpass')
    client.post(f'/billing/plans/{plan.id}/buy')
    inv = Invoice.query.filter_by(org_id=associate_admin.org_id).first()

    client.get('/logout')
    _login(client, master_admin, 'masterpass')

    resp = client.post(
        f'/master/invoices/{inv.id}/cancel',
        data={'reason': 'test cancel'},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    db.session.refresh(inv)
    assert inv.status == 'cancelled'
    assert inv.cancellation_reason == 'test cancel'


def test_associate_cannot_mark_paid(client, app, db,
                                    associate_admin, plan):
    _login(client, associate_admin, 'assocpass')
    client.post(f'/billing/plans/{plan.id}/buy')
    inv = Invoice.query.filter_by(org_id=associate_admin.org_id).first()

    resp = client.post(
        f'/master/invoices/{inv.id}/mark-paid',
        data={'payment_method': 'cash', 'payment_reference': 'X'},
    )
    assert resp.status_code == 403


def test_associate_cannot_see_other_orgs_invoice(client, app, db,
                                                 associate_admin,
                                                 second_org, plan):
    from app.services import billing as svc
    other_inv, _ = svc.create_invoice(second_org, plan)

    _login(client, associate_admin, 'assocpass')
    resp = client.get(f'/billing/invoices/{other_inv.id}')
    assert resp.status_code == 404
    
    
def test_associate_can_download_own_invoice_pdf(client, app, db,
                                                associate_admin, plan):
    _login(client, associate_admin, 'assocpass')
    client.post(f'/billing/plans/{plan.id}/buy')

    inv = Invoice.query.filter_by(org_id=associate_admin.org_id).first()
    assert inv is not None

    resp = client.get(f'/billing/invoices/{inv.id}.pdf')
    assert resp.status_code == 200
    assert resp.mimetype == 'application/pdf'
    assert resp.data.startswith(b'%PDF-')
    assert f'{inv.number}.pdf' in resp.headers.get('Content-Disposition', '')


def test_associate_cannot_download_other_org_invoice_pdf(client, app, db,
                                                         associate_admin,
                                                         second_org, plan):
    from app.services import billing as svc
    other_inv, _ = svc.create_invoice(second_org, plan)

    _login(client, associate_admin, 'assocpass')
    resp = client.get(f'/billing/invoices/{other_inv.id}.pdf')
    assert resp.status_code == 404


def test_master_can_download_any_invoice_pdf(client, app, db, master_admin,
                                             associate_admin, plan):
    _login(client, associate_admin, 'assocpass')
    client.post(f'/billing/plans/{plan.id}/buy')
    inv = Invoice.query.filter_by(org_id=associate_admin.org_id).first()

    client.get('/logout')
    _login(client, master_admin, 'masterpass')

    resp = client.get(f'/master/invoices/{inv.id}.pdf')
    assert resp.status_code == 200
    assert resp.mimetype == 'application/pdf'
    assert resp.data.startswith(b'%PDF-')


def test_unauthenticated_invoice_pdf_redirects(client, app, db,
                                                associate_admin, plan):
    from app.services import billing as svc
    inv, _ = svc.create_invoice(associate_admin.organization, plan)
    resp = client.get(f'/billing/invoices/{inv.id}.pdf')
    assert resp.status_code in (302, 401)