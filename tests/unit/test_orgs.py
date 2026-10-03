import pytest
from app.models import Organization, User
from app.services import orgs as svc


def test_create_associate(app, db, master_org):
    org, admin = svc.create_associate(
        name='Kampalafit', slug='kampalafit', brand_name='Kampalafit',
        admin_email='owner@kampalafit.test', admin_password='pass12345',
    )
    assert org.id is not None
    assert org.is_master is False
    assert org.parent_id == master_org.id
    assert admin.role == 'associate_admin'
    assert admin.org_id == org.id
    assert admin.check_password('pass12345')


def test_create_rejects_duplicate_slug(app, db, master_org):
    svc.create_associate(
        name='A', slug='dup', brand_name='A',
        admin_email='a@a.test', admin_password='pass12345')
    with pytest.raises(svc.OrgError, match='already in use'):
        svc.create_associate(
            name='B', slug='dup', brand_name='B',
            admin_email='b@b.test', admin_password='pass12345')


def test_create_rejects_duplicate_email(app, db, master_org):
    svc.create_associate(
        name='A', slug='aaa', brand_name='A',
        admin_email='same@x.test', admin_password='pass12345')
    with pytest.raises(svc.OrgError, match='already registered'):
        svc.create_associate(
            name='B', slug='bbb', brand_name='B',
            admin_email='same@x.test', admin_password='pass12345')


@pytest.mark.parametrize('slug', ['', 'A', 'BAD SLUG', '-lead', 'trail-',
                                   'has_underscore', 'x' * 60])
def test_slug_validation(slug, app, db, master_org):
    with pytest.raises(svc.OrgError):
        svc.create_associate(
            name='X', slug=slug, brand_name='X',
            admin_email=f'x{slug}@t.test', admin_password='pass12345')


def test_short_password_rejected(app, db, master_org):
    with pytest.raises(svc.OrgError, match='at least 8'):
        svc.create_associate(
            name='X', slug='xxx', brand_name='X',
            admin_email='x@x.test', admin_password='short')


def test_suspend_cancels_queue(app, db, associate_org):
    from app.models import SendQueue, Campaign
    camp = Campaign(org_id=associate_org.id, name='t', body='t',
                    sender_id='X', status='queued')
    db.session.add(camp)
    db.session.flush()
    db.session.add(SendQueue(campaign_id=camp.id, org_id=associate_org.id,
                             status='pending'))
    db.session.commit()

    svc.suspend_associate(associate_org, reason='test')

    assert associate_org.status == 'suspended'
    assert SendQueue.query.filter_by(org_id=associate_org.id,
                                     status='pending').count() == 0


def test_cannot_suspend_master(app, db, master_org):
    with pytest.raises(svc.OrgError):
        svc.suspend_associate(master_org)


# ---------------------------------------------------------------------------
# Brand name length cap (regression: sender_id used to be String(11), but
# brand_name can be up to 20 chars, and create_associate did not validate
# length at all. A 21-char brand_name silently produced a String(11)
# sender_id downstream and blew up on first campaign insert.)
# ---------------------------------------------------------------------------

def test_create_associate_rejects_long_brand_name(db, master_org):
    """brand_name is capped at 20 chars to match the SMS prefix limit."""
    with pytest.raises(svc.OrgError, match='20 characters'):
        svc.create_associate(
            name='Test Co',
            slug='testco',
            brand_name='A' * 21,
            admin_email='admin@testco.co.ug',
            admin_password='password123',
        )


def test_create_associate_accepts_20_char_brand_name(db, master_org):
    """Exactly 20 is fine — only 21+ is rejected."""
    org, admin = svc.create_associate(
        name='Boundary Co',
        slug='boundaryco',
        brand_name='B' * 20,
        admin_email='admin@boundary.co.ug',
        admin_password='password123',
    )
    assert org.brand_name == 'B' * 20