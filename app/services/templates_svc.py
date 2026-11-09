from app.extensions import db
from app.models import MessageTemplate
from app.services.audit import log as audit
from app.permissions import department_filter


class TemplateError(Exception):
    pass


def create_template(org, *, name, body, department=None):
    if not name or not body:
        raise TemplateError('Name and body are required.')
    t = MessageTemplate(org_id=org.id, name=name.strip(), body=body.strip(), department=department)
    db.session.add(t)
    db.session.commit()
    audit('template_create', t.name)
    return t


def update_template(org, tid, *, name, body, user=None):
    t = MessageTemplate.query.filter_by(id=tid, org_id=org.id).first()
    if not t:
        raise TemplateError('Template not found.')
    if user is not None and getattr(user, 'department', None) is not None:
        if t.department not in (user.department, None):
            raise TemplateError('Template not found.')
    t.name = name.strip()
    t.body = body.strip()
    db.session.commit()
    return t


def delete_template(org, tid, *, user=None):
    t = MessageTemplate.query.filter_by(id=tid, org_id=org.id).first()
    if not t:
        raise TemplateError('Template not found.')
    if user is not None and getattr(user, 'department', None) is not None:
        if t.department not in (user.department, None):
            raise TemplateError('Template not found.')
    db.session.delete(t)
    db.session.commit()
    audit('template_delete', t.name)


def list_templates(org, user=None):
    """Return templates visible to the user based on department.

    When user has a department, returns department-matching templates
    plus shared (department IS NULL). When user is None or has no
    department, returns all templates in the org.
    """
    query = MessageTemplate.query.filter_by(org_id=org.id)
    query = department_filter(query, MessageTemplate, user)
    return query.order_by(MessageTemplate.id.desc()).all()

def get_for_user(org, tid, user):
    """Fetch a single template by id, returning None if not visible.

    Returns None when:
      - no template with this id in this org
      - user.department is set and template.department is a different dept
    """
    t = MessageTemplate.query.filter_by(id=tid, org_id=org.id).first()
    if t is None:
        return None
    if user is not None and getattr(user, 'department', None) is not None:
        if t.department not in (user.department, None):
            return None
    return t
