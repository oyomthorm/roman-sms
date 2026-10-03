import pytest
from app.models import Group, Contact
from app.services import groups as svc


def test_create_group(app, db, associate_org):
    g = svc.create(associate_org, name='VIP')
    assert g.id is not None
    assert g.name == 'VIP'
    assert g.org_id == associate_org.id


def test_create_duplicate_name_rejected(app, db, associate_org):
    svc.create(associate_org, name='VIP')
    with pytest.raises(svc.GroupError, match='already exists'):
        svc.create(associate_org, name='VIP')


def test_duplicate_is_case_insensitive(app, db, associate_org):
    svc.create(associate_org, name='VIP')
    with pytest.raises(svc.GroupError, match='already exists'):
        svc.create(associate_org, name='vip')


def test_blank_name_rejected(app, db, associate_org):
    with pytest.raises(svc.GroupError, match='required'):
        svc.create(associate_org, name='   ')


def test_name_too_long_rejected(app, db, associate_org):
    with pytest.raises(svc.GroupError, match='80'):
        svc.create(associate_org, name='x' * 81)


def test_find_or_create_is_idempotent(app, db, associate_org):
    g1, created1 = svc.find_or_create(associate_org, 'Newsletter')
    g2, created2 = svc.find_or_create(associate_org, 'newsletter')
    assert created1 is True
    assert created2 is False
    assert g1.id == g2.id


def test_rename_updates_contact_display(app, db, associate_org):
    g = svc.create(associate_org, name='Old')
    c = Contact(org_id=associate_org.id, phone='256700000001',
                name='Alice', group_id=g.id)
    db.session.add(c)
    db.session.commit()

    svc.update(associate_org, g.id, name='New')
    db.session.refresh(c)
    assert c.group.name == 'New'


def test_rename_to_duplicate_rejected(app, db, associate_org):
    svc.create(associate_org, name='A')
    b = svc.create(associate_org, name='B')
    with pytest.raises(svc.GroupError, match='already exists'):
        svc.update(associate_org, b.id, name='A')


def test_delete_with_contacts_requires_target(app, db, associate_org):
    g1 = svc.create(associate_org, name='Source')
    g2 = svc.create(associate_org, name='Target')
    c = Contact(org_id=associate_org.id, phone='256700000002',
                group_id=g1.id)
    db.session.add(c)
    db.session.commit()

    moved, target = svc.delete(associate_org, g1.id,
                               move_to_group_id=g2.id)
    assert moved == 1
    assert target.id == g2.id
    db.session.refresh(c)
    assert c.group_id == g2.id
    assert Group.query.filter_by(id=g1.id).first() is None


def test_delete_without_target_detaches_contacts(app, db, associate_org):
    g = svc.create(associate_org, name='Detach')
    c = Contact(org_id=associate_org.id, phone='256700000003',
                group_id=g.id)
    db.session.add(c)
    db.session.commit()

    moved, target = svc.delete(associate_org, g.id)
    assert moved == 1
    assert target is None
    db.session.refresh(c)
    assert c.group_id is None


def test_delete_cannot_target_itself(app, db, associate_org):
    g = svc.create(associate_org, name='Self')
    with pytest.raises(svc.GroupError, match='being deleted'):
        svc.delete(associate_org, g.id, move_to_group_id=g.id)


def test_same_group_name_allowed_across_orgs(app, db,
                                             associate_org, second_org):
    a = svc.create(associate_org, name='Shared')
    b = svc.create(second_org, name='Shared')
    assert a.id != b.id
    assert a.org_id == associate_org.id
    assert b.org_id == second_org.id


def test_group_lookup_is_scoped_to_org(app, db,
                                       associate_org, second_org):
    a = svc.create(associate_org, name='VIP')
    # Looking up by id from another org must return None.
    assert svc.get(second_org, a.id) is None
    assert svc.get(associate_org, a.id) is not None