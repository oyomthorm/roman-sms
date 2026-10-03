"""
Test factories for Roman SMS.

Both styles are supported:
  - Function style: OrgFactory(...), UserFactory(org=o), etc.
  - Helper style:   make_org(...), make_user(...), etc.

Every factory commits immediately so tests can use the returned object
without an extra db.session.commit().
"""
import uuid
from datetime import datetime, timedelta

from app.extensions import db
from app.models import (Organization, User, Plan, Subscription,
                        Contact, MessageTemplate, Campaign, MessageLog,
                        WalletTransaction, OptOut)


_counter = {'n': 0}


def _next():
    _counter['n'] += 1
    return _counter['n']


def _reset():
    _counter['n'] = 0


# --------------------------------------------------------------------------
# Factory-style constructors (used by the test suite)
# --------------------------------------------------------------------------

def OrgFactory(**kwargs):
    n = _next()
    defaults = dict(
        name=f'Test Org {n}',
        slug=f'test-org-{n}',
        brand_name=f'Brand{n}',
        status='active',
        is_master=False,
    )
    defaults.update(kwargs)
    org = Organization(**defaults)
    db.session.add(org)
    db.session.commit()
    return org


def UserFactory(org=None, **kwargs):
    n = _next()
    if org is None and 'org_id' not in kwargs:
        org = OrgFactory()

    org_id = kwargs.pop('org_id', org.id if org is not None else None)
    email = kwargs.pop('email', f'user{n}@test.local')
    password = kwargs.pop('password', 'testpass123')
    role = kwargs.pop('role', 'associate_admin')
    full_name = kwargs.pop('full_name', f'User {n}')

    user = User(
        email=email,
        full_name=full_name,
        role=role,
        org_id=org_id,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def PlanFactory(**kwargs):
    n = _next()
    defaults = dict(
        name=f'Plan {n}',
        price=50000,
        currency='UGX',
        credits=1000,
        validity_days=30,
        max_contacts=10000,
        max_per_minute=60,
        max_per_day=5000,
        is_active=True,
    )
    defaults.update(kwargs)
    plan = Plan(**defaults)
    db.session.add(plan)
    db.session.commit()
    return plan


def ContactFactory(**kwargs):
    n = _next()
    defaults = dict(
        phone=f'2567{n:08d}',
        name=f'Contact {n}',
    )
    defaults.update(kwargs)
    contact = Contact(**defaults)
    db.session.add(contact)
    db.session.commit()
    return contact


# --------------------------------------------------------------------------
# Helper-style constructors (kept for compatibility)
# --------------------------------------------------------------------------

def make_org(name='TestOrg', brand=None, status='active', is_master=False,
             parent=None):
    slug = f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}"
    org = Organization(
        name=name, slug=slug, brand_name=brand or name,
        status=status, is_master=is_master,
        parent_id=parent.id if parent else None,
    )
    db.session.add(org)
    db.session.commit()
    return org


def make_user(org, email=None, password='pass1234',
              role='associate_admin'):
    email = email or f'{org.slug}-{role}@test.local'
    u = User(email=email, full_name=role, role=role, org_id=org.id)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return u


def make_contact(org, phone, name='Alice', group=None,
                 group_id=None, opted_out=False):
    c = Contact(org_id=org.id, phone=phone, name=name,
                group_id=group_id, opted_out=opted_out)
    db.session.add(c)
    db.session.commit()
    return c


def make_template(org, name='Welcome', body='Hello {{name}}'):
    t = MessageTemplate(org_id=org.id, name=name, body=body)
    db.session.add(t)
    db.session.commit()
    return t


def make_campaign(org, user, name='Test campaign',
                  body='Hello {{name}}', group_id=None,
                  group_name=None, sender_id='ROMANSMS',
                  status='draft', total=0):
    c = Campaign(
        org_id=org.id, name=name, body=body, sender_id=sender_id,
        group_filter=group_name, status=status, total=total,
        created_by=user.id,
    )
    db.session.add(c)
    db.session.commit()
    return c


def make_log(org, campaign, phone, body='Hello', status='pending'):
    m = MessageLog(org_id=org.id, campaign_id=campaign.id,
                   phone=phone, body=body, status=status)
    db.session.add(m)
    db.session.commit()
    return m


def make_ledger_row(org, delta, reason='test', balance_after=None,
                    reference=None, actor_id=None):
    if balance_after is None:
        last = (WalletTransaction.query.filter_by(org_id=org.id)
                .order_by(WalletTransaction.id.desc()).first())
        balance_after = (last.balance_after if last else 0) + delta
    tx = WalletTransaction(
        org_id=org.id, delta=delta, reason=reason,
        balance_after=balance_after, reference=reference,
        actor_id=actor_id,
    )
    db.session.add(tx)
    db.session.commit()
    return tx


def add_optout(phone, reason='test'):
    if OptOut.query.filter_by(phone=phone).first():
        return
    db.session.add(OptOut(phone=phone, reason=reason))
    db.session.commit()