"""
Organization service.

Every write to Organization or User through the master console goes
through here so validation, slug rules, system-org protection, and audit
logging stay consistent.

Three org kinds:
  is_master=True   — the operator (you)
  is_system=True   — internal sending identity ("Roman SMS Platform")
  neither          — associates (paying clients)
"""
import re
from app.extensions import db
from app.models import Organization, User, SendQueue
from app.services.audit import log as audit


SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$')


class OrgError(Exception):
    pass


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------

def list_associates():
    """All associate orgs — never master, never system."""
    return (Organization.query
            .filter_by(is_master=False, is_system=False)
            .order_by(Organization.name)
            .all())


def get_associate_or_404(org_id):
    """Fetch an associate. Refuses master and system orgs."""
    org = db.session.get(Organization, org_id)
    if not org or org.is_master or org.is_system:
        return None
    return org


def get_system_org():
    """The internal sending identity. Used by master platform views."""
    return Organization.query.filter_by(is_system=True).first()


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def _validate_slug(slug):
    slug = (slug or '').strip().lower()
    if not SLUG_RE.match(slug):
        raise OrgError(
            'Slug must be 3-50 characters, lowercase letters, numbers, '
            'and dashes only (no leading or trailing dash).'
        )
    return slug


def _validate_password(pw):
    if not pw or len(pw) < 8:
        raise OrgError('Password must be at least 8 characters.')
    return pw


def _refuse_if_protected(org):
    if not org:
        raise OrgError('Organization not found.')
    if org.is_master:
        raise OrgError('Cannot modify the master organization.')
    if org.is_system:
        raise OrgError('Cannot modify the system organization.')


# --------------------------------------------------------------------------
# Create / update
# --------------------------------------------------------------------------

def create_associate(*, name, slug, brand_name, admin_email,
                     admin_password, admin_full_name=None,
                     contact_email=None, contact_phone=None,
                     district_id=None,
                     actor_id=None):
    """
    Create an associate org and its first associate_admin.
    Both are created in one transaction; failure rolls back everything.
    """

    name = (name or '').strip()
    brand_name = (brand_name or name).strip()
    admin_email = (admin_email or '').strip().lower()

    if not name:
        raise OrgError('Organization name is required.')
    if not admin_email:
        raise OrgError('Admin email is required.')
    if len(brand_name) > 20:
        raise OrgError('Brand name must be 20 characters or fewer '
                       '(it becomes the SMS prefix).')
    slug = _validate_slug(slug)
    admin_password = _validate_password(admin_password)
 
    if Organization.query.filter_by(slug=slug).first():
        raise OrgError(f'Slug "{slug}" is already in use.')
    if User.query.filter_by(email=admin_email).first():
        raise OrgError(f'Email "{admin_email}" is already registered.')

    master = Organization.query.filter_by(is_master=True).first()
    if not master:
        raise OrgError('Master organization missing. Run seed.')

    org = Organization(
        name=name, slug=slug, brand_name=brand_name,
        status='active', is_master=False, is_system=False,
        parent_id=master.id,
        contact_email=(contact_email or '').strip() or None,
        contact_phone=(contact_phone or '').strip() or None,
        district_id=district_id or None,
    )
    db.session.add(org)
    db.session.flush()

    admin = User(
        email=admin_email,
        full_name=(admin_full_name or f'{name} Admin').strip(),
        role='associate_admin',
        org_id=org.id,
    )
    admin.set_password(admin_password)
    db.session.add(admin)
    db.session.commit()

    audit('org_create', f'org={org.slug} admin={admin_email}',
          org_id=org.id, actor_id=actor_id)
    return org, admin


def update_associate(org, *, name=None, brand_name=None,
                     contact_email=None, contact_phone=None,
                     district_id=None,
                     actor_id=None):
    _refuse_if_protected(org)

    if name is not None:
        name = name.strip()
        if not name:
            raise OrgError('Name cannot be empty.')
        org.name = name

    if brand_name is not None:
        brand_name = brand_name.strip()
        if not brand_name:
            raise OrgError('Brand name cannot be empty.')
        if len(brand_name) > 20:
            raise OrgError('Brand name must be 20 characters or fewer '
                           '(it becomes the SMS prefix).')
        org.brand_name = brand_name

    if contact_email is not None:
        org.contact_email = contact_email.strip() or None

    if contact_phone is not None:
        org.contact_phone = contact_phone.strip() or None

    if district_id is not None:
        org.district_id = district_id or None

    db.session.commit()
    audit('org_update', f'org={org.slug}', org_id=org.id, actor_id=actor_id)
    return org


# --------------------------------------------------------------------------
# Status changes
# --------------------------------------------------------------------------

def suspend_associate(org, *, actor_id=None, reason=None):
    """Cancel any pending send jobs immediately."""
    _refuse_if_protected(org)

    org.status = 'suspended'

    (SendQueue.query
     .filter_by(org_id=org.id, status='pending')
     .update({'status': 'failed', 'last_error': 'org suspended'},
             synchronize_session=False))

    db.session.commit()
    audit('org_suspend',
          f'org={org.slug} reason={reason or "-"}',
          org_id=org.id, actor_id=actor_id)
    return org


def activate_associate(org, *, actor_id=None):
    _refuse_if_protected(org)

    org.status = 'active'
    db.session.commit()
    audit('org_activate', f'org={org.slug}',
          org_id=org.id, actor_id=actor_id)
    return org


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------

def reset_admin_password(org, user_id, new_password, *, actor_id=None):
    """Reset an associate user's password from the master console."""
    _refuse_if_protected(org)

    user = User.query.filter_by(id=user_id, org_id=org.id).first()
    if not user:
        raise OrgError('User not found in that organization.')

    user.set_password(_validate_password(new_password))
    db.session.commit()
    audit('user_password_reset', f'org={org.slug} user={user.email}',
          org_id=org.id, actor_id=actor_id)
    return user