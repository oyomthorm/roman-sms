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
from datetime import datetime
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
                     district_id=None, vertical=None,
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
        vertical=(vertical if vertical in ('school', 'business') else None),
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
                     district_id=None, vertical=None,
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

    if vertical is not None:
        # Empty string -> None (unclassified). Only 'school'/'business' accepted.
        if vertical == '':
            org.vertical = None
        elif vertical in ('school', 'business'):
            org.vertical = vertical
        else:
            raise OrgError('Vertical must be "school", "business", or unset.')

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

# --------------------------------------------------------------------------
# School user CRUD -- create/edit/delete/reset within an org (A5)
# --------------------------------------------------------------------------
#
# Permission model (see docs/DEPARTMENTS.md §1):
#   - These functions are for a school's own admin (role='associate_admin',
#     department=None) to manage users in their own org.
#   - Master does not create school users via these functions. Master's only
#     user-level action on an org is reset_admin_password (existing).
#   - The route layer enforces WHO can call these (school_admin_required);
#     these functions enforce WHAT is valid.

DEPARTMENTS = (None, 'bursar', 'dos', 'dean', 'ht')
USER_ROLES = ('associate_admin', 'user')


def list_users(org):
    """All users in this org, alphabetical by email."""
    return (User.query
            .filter_by(org_id=org.id)
            .order_by(User.email)
            .all())


def _validate_department(department):
    if department not in DEPARTMENTS:
        raise OrgError(
            'Invalid department. Choose one of: '
            'shared (none), bursar, dos, dean, ht.')
    return department


def _validate_user_role(role):
    if role not in USER_ROLES:
        raise OrgError(
            "Invalid role. Must be 'associate_admin' or 'user'.")
    return role


def _validate_role_department_combo(role, department):
    """Dept-scoped admins are not allowed.

    associate_admin is always dept=None (sees everything in the org).
    To create a dept-scoped user, use role='user'.
    """
    if role == 'associate_admin' and department is not None:
        raise OrgError(
            'A school admin cannot be scoped to a department. '
            'Create a regular user (role="user") with that department instead.')
    return role, department


def _validate_email_unique(email, exclude_id=None):
    email = (email or '').strip().lower()
    if not email:
        raise OrgError('Email is required.')
    if '@' not in email or '.' not in email.split('@')[-1]:
        raise OrgError('Enter a valid email address.')
    q = User.query.filter(User.email == email)
    if exclude_id:
        q = q.filter(User.id != exclude_id)
    if q.first():
        raise OrgError(f'Email "{email}" is already registered.')
    return email


def create_user(org, *, email, full_name, password,
                role='associate_admin', department=None, actor_id=None):
    """Create a new user in this org.

    role: 'associate_admin' (school admin, dept=None) or 'user' (dept-scoped).
    department: None or one of DEPARTMENTS. Ignored-as-None for admin role.
    """
    _refuse_if_protected(org)

    email = _validate_email_unique(email)
    role = _validate_user_role(role)
    department = _validate_department(department)
    _validate_role_department_combo(role, department)
    password = _validate_password(password)

    full_name = (full_name or '').strip()
    if not full_name:
        raise OrgError('Full name is required.')

    user = User(
        email=email,
        full_name=full_name,
        role=role,
        org_id=org.id,
        department=department,
        status='active',
        is_active_flag=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    audit('user_create',
          f'org={org.slug} email={email} role={role} dept={department or "shared"}',
          org_id=org.id, actor_id=actor_id)
    return user


def update_user(org, user_id, *, full_name=None, email=None,
                department=None, actor_id=None):
    """Update a user's name, email, or department. Never changes role.

    Role changes are a separate feature (not built yet).
    """
    _refuse_if_protected(org)

    user = User.query.filter_by(id=user_id, org_id=org.id).first()
    if not user:
        raise OrgError('User not found in that organization.')

    if full_name is not None:
        full_name = full_name.strip()
        if not full_name:
            raise OrgError('Full name cannot be empty.')
        user.full_name = full_name

    if email is not None:
        new_email = _validate_email_unique(email, exclude_id=user.id)
        if new_email != user.email:
            user.email = new_email

    if department is not None or department == None:  # always applied when kwarg present
        # Note: caller must pass department= explicitly to change it; omitting
        # the kwarg leaves it unchanged. We can't distinguish "not provided"
        # from "set to None" in this signature, so callers who want to clear
        # department must pass department=None explicitly.
        if department != '':
            new_dept = None if department is None else department
            _validate_department(new_dept)
            _validate_role_department_combo(user.role, new_dept)
            user.department = new_dept

    db.session.commit()
    audit('user_update',
          f'org={org.slug} email={user.email}',
          org_id=org.id, actor_id=actor_id)
    return user


def _discover_user_fks():
    """Return [(schema, table, column, is_nullable), ...] for FKs to user.id.

    Dialect-aware:
      - Postgres: information_schema.table_constraints (global, one query)
      - SQLite:   PRAGMA foreign_key_list per table (per-table, metadata for nullable)
    """
    from sqlalchemy import text
    dialect = db.engine.name
    if dialect == 'postgresql':
        rows = db.session.execute(text("""
            SELECT kcu.table_schema, kcu.table_name, kcu.column_name,
                   CASE WHEN cols.is_nullable = 'NO' THEN false ELSE true END
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
            JOIN information_schema.columns cols
              ON cols.table_schema = kcu.table_schema
             AND cols.table_name = kcu.table_name
             AND cols.column_name = kcu.column_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_schema = 'public'
              AND ccu.table_name = 'user'
              AND ccu.column_name = 'id'
        """)).fetchall()
        return [(r[0], r[1], r[2], r[3]) for r in rows]
    elif dialect == 'sqlite':
        out = []
        for tbl_name, tbl in db.metadata.tables.items():
            pragma = db.session.execute(
                text(f'PRAGMA foreign_key_list("{tbl_name}")')).fetchall()
            for row in pragma:
                # PRAGMA foreign_key_list columns:
                #   id, seq, table, from, to, on_update, on_delete, match
                if row[2] == 'user' and row[4] == 'id':
                    col_name = row[3]
                    col_obj = tbl.columns.get(col_name)
                    nullable = True
                    if col_obj is not None:
                        nullable = col_obj.nullable if col_obj.nullable is not None else True
                    out.append((None, tbl_name, col_name, nullable))
        return out
    else:
        raise RuntimeError(f'Unsupported dialect for FK enumeration: {dialect}')


def _delete_user_fk_aware(uid):
    """Remove all FK references to uid, then let caller delete the User row.

    NOT NULL FKs are DELETEd (personal rows: chat_read_state, etc.)
    Nullable FKs are SET NULL (financial/audit attribution: wallet_transaction, etc.)
    Works on Postgres and SQLite via _discover_user_fks().
    """
    from sqlalchemy import text
    for tbl_schema, tbl_name, col_name, nullable in _discover_user_fks():
        if tbl_schema:
            tbl = f'"{tbl_schema}"."{tbl_name}"'
        else:
            tbl = f'"{tbl_name}"'
        col = f'"{col_name}"'
        if nullable:
            db.session.execute(
                text(f'UPDATE {tbl} SET {col} = NULL WHERE {col} = :uid'),
                {'uid': uid})
        else:
            db.session.execute(
                text(f'DELETE FROM {tbl} WHERE {col} = :uid'),
                {'uid': uid})

def delete_user(org, user_id, *, actor_id=None):
    """FK-aware delete of a user. Refuses to remove the last school admin."""
    _refuse_if_protected(org)

    user = User.query.filter_by(id=user_id, org_id=org.id).first()
    if not user:
        raise OrgError('User not found in that organization.')

    if user.role == 'associate_admin':
        admin_count = User.query.filter_by(
            org_id=org.id, role='associate_admin').count()
        if admin_count <= 1:
            raise OrgError(
                'Cannot delete the last school admin. '
                'Create another admin first.')

    email = user.email
    _delete_user_fk_aware(user.id)
    db.session.delete(user)
    db.session.commit()
    audit('user_delete',
          f'org={org.slug} email={email}',
          org_id=org.id, actor_id=actor_id)

# --------------------------------------------------------------------------
# User lifecycle -- suspend/terminate/reactivate (#46)
# --------------------------------------------------------------------------

def suspend_user(org, user_id, *, actor_id=None):
    """Set status='suspended'. Login stays allowed; sends are blocked at
    routes/campaigns.py::new. Reactivate to restore send permission."""
    _refuse_if_protected(org)
    user = User.query.filter_by(id=user_id, org_id=org.id).first()
    if not user:
        raise OrgError('User not found in that organization.')
    if user.id == actor_id:
        raise OrgError('You cannot suspend yourself.')
    if user.status == 'suspended':
        raise OrgError('User is already suspended.')
    if user.status == 'terminated':
        raise OrgError('User is terminated. Reactivate them first.')
    if user.role == 'associate_admin':
        admin_count = User.query.filter_by(
            org_id=org.id, role='associate_admin', status='active').count()
        if admin_count <= 1:
            raise OrgError('Cannot suspend the last active school admin.')
    user.status = 'suspended'
    user.status_changed_at = datetime.utcnow()
    db.session.commit()
    audit('user_suspend', f'org={org.slug} email={user.email}',
          org_id=org.id, actor_id=actor_id)
    return user


def terminate_user(org, user_id, *, actor_id=None):
    """Set status='terminated' AND is_active_flag=False (login blocked)."""
    _refuse_if_protected(org)
    user = User.query.filter_by(id=user_id, org_id=org.id).first()
    if not user:
        raise OrgError('User not found in that organization.')
    if user.id == actor_id:
        raise OrgError('You cannot terminate yourself.')
    if user.status == 'terminated':
        raise OrgError('User is already terminated.')
    if user.role == 'associate_admin':
        admin_count = User.query.filter_by(
            org_id=org.id, role='associate_admin', status='active').count()
        if admin_count <= 1:
            raise OrgError('Cannot terminate the last active school admin.')
    user.status = 'terminated'
    user.status_changed_at = datetime.utcnow()
    user.is_active_flag = False
    db.session.commit()
    audit('user_terminate', f'org={org.slug} email={user.email}',
          org_id=org.id, actor_id=actor_id)
    return user


def reactivate_user(org, user_id, *, actor_id=None):
    """Set status='active' AND is_active_flag=True (login allowed)."""
    _refuse_if_protected(org)
    user = User.query.filter_by(id=user_id, org_id=org.id).first()
    if not user:
        raise OrgError('User not found in that organization.')
    if user.status == 'active':
        raise OrgError('User is already active.')
    user.status = 'active'
    user.status_changed_at = datetime.utcnow()
    user.is_active_flag = True
    db.session.commit()
    audit('user_reactivate', f'org={org.slug} email={user.email}',
          org_id=org.id, actor_id=actor_id)
    return user

# --------------------------------------------------------------------------
# User detail helper (#47)
# --------------------------------------------------------------------------

def get_user(org, user_id):
    """Fetch a single user in this org, or None."""
    return User.query.filter_by(id=user_id, org_id=org.id).first()


def get_user_activity(org, user_id):
    """Aggregate activity for one user. Returns dict with counts + recent items."""
    from datetime import datetime, timedelta
    from app.models import Campaign, CampaignSchedule, AuditLog

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    q_campaigns = Campaign.query.filter_by(org_id=org.id, created_by=user_id)
    campaign_count = q_campaigns.count()
    campaigns_30d = q_campaigns.filter(
        Campaign.created_at > thirty_days_ago).count()

    schedules_q = CampaignSchedule.query.filter_by(
        org_id=org.id, created_by=user_id)
    schedules_active = schedules_q.filter(
        CampaignSchedule.status == 'active').count()

    recent_campaigns = (
        q_campaigns.order_by(Campaign.id.desc()).limit(10).all())
    recent_schedules = (
        schedules_q.order_by(CampaignSchedule.id.desc()).limit(10).all())
    recent_audit = (
        AuditLog.query
        .filter_by(actor_id=user_id, org_id=org.id)
        .order_by(AuditLog.id.desc()).limit(20).all())

    return {
        'campaign_count': campaign_count,
        'campaigns_30d': campaigns_30d,
        'schedules_active': schedules_active,
        'recent_campaigns': recent_campaigns,
        'recent_schedules': recent_schedules,
        'recent_audit': recent_audit,
    }
