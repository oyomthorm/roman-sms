"""
Group service. Everything that touches contact groups goes through here,
so uniqueness, renaming, and cascading behaviour stay consistent.
"""
from app.extensions import db
from app.models import Group, Contact
from app.services.audit import log as audit


class GroupError(Exception):
    pass


def list_groups(org):
    """Return [(group, contact_count), ...] sorted by name."""
    groups = (Group.query
              .filter_by(org_id=org.id)
              .order_by(Group.name)
              .all())
    counts = dict(
        db.session.query(Contact.group_id, db.func.count(Contact.id))
        .filter(Contact.org_id == org.id, Contact.group_id.isnot(None))
        .group_by(Contact.group_id)
        .all()
    )
    return [(g, counts.get(g.id, 0)) for g in groups]


def list_names(org):
    """Return group names only. Used by legacy callers."""
    return [g.name for g, _ in list_groups(org)]


def get(org, group_id):
    return Group.query.filter_by(id=group_id, org_id=org.id).first()


def get_or_404(org, group_id):
    g = get(org, group_id)
    if not g:
        raise GroupError('Group not found.')
    return g


def find_by_name(org, name):
    """Case-insensitive lookup within an org."""
    if not name:
        return None
    return (Group.query
            .filter(Group.org_id == org.id,
                    db.func.lower(Group.name) == name.strip().lower())
            .first())


def _validate_name(org, name, exclude_id=None):
    name = (name or '').strip()
    if not name:
        raise GroupError('Group name is required.')
    if len(name) > 80:
        raise GroupError('Group name must be 80 characters or fewer.')

    q = Group.query.filter(
        Group.org_id == org.id,
        db.func.lower(Group.name) == name.lower(),
    )
    if exclude_id:
        q = q.filter(Group.id != exclude_id)
    if q.first():
        raise GroupError(f'A group named "{name}" already exists.')
    return name


def create(org, *, name, description=None, actor_id=None):
    name = _validate_name(org, name)
    group = Group(org_id=org.id, name=name,
                  description=(description or '').strip() or None)
    db.session.add(group)
    db.session.commit()
    audit('group_create', f'name={name}', org_id=org.id, actor_id=actor_id)
    return group


def find_or_create(org, name, *, actor_id=None):
    """
    Used by the importer and by manual contact entry.
    Returns (group, created) where created is True if a new row was made.
    Does NOT commit — the caller manages the transaction.
    """
    name = (name or '').strip()
    if not name:
        return None, False
    existing = find_by_name(org, name)
    if existing:
        return existing, False
    group = Group(org_id=org.id, name=name)
    db.session.add(group)
    db.session.flush()
    return group, True


def update(org, group_id, *, name, description=None, actor_id=None):
    group = get_or_404(org, group_id)
    name = _validate_name(org, name, exclude_id=group.id)
    group.name = name
    group.description = (description or '').strip() or None
    db.session.commit()
    audit('group_update', f'id={group.id} name={name}',
          org_id=org.id, actor_id=actor_id)
    return group


def delete(org, group_id, *, move_to_group_id=None, actor_id=None):
    """
    Delete a group. Contacts move to move_to_group_id, or detach if None.
    Returns (moved_count, target_group_or_none).
    """
    group = get_or_404(org, group_id)

    target = None
    if move_to_group_id:
        target = Group.query.filter_by(id=move_to_group_id,
                                       org_id=org.id).first()
        if not target:
            raise GroupError('Target group not found.')
        if target.id == group.id:
            raise GroupError('Cannot move contacts into the group being deleted.')

    q = Contact.query.filter_by(org_id=org.id, group_id=group.id)
    moved = q.count()
    q.update({'group_id': target.id if target else None},
             synchronize_session=False)

    name = group.name
    db.session.delete(group)
    db.session.commit()

    audit('group_delete',
          f'name={name} moved={moved} '
          f'to={target.name if target else "none"}',
          org_id=org.id, actor_id=actor_id)
    return moved, target


def contacts_in(org, group_id):
    return (Contact.query
            .filter_by(org_id=org.id, group_id=group_id)
            .order_by(Contact.id.desc())
            .all())


def attach(org, contact_ids, group_id):
    """Move a list of contacts into a group (or out if group_id is None)."""
    if group_id is not None:
        get_or_404(org, group_id)
    n = (Contact.query
         .filter(Contact.org_id == org.id, Contact.id.in_(contact_ids))
         .update({'group_id': group_id}, synchronize_session=False))
    db.session.commit()
    return n