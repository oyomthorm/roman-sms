from app.extensions import db
from app.models import MessageTemplate
from app.services.audit import log as audit


class TemplateError(Exception):
    pass


def create_template(org, *, name, body):
    if not name or not body:
        raise TemplateError('Name and body are required.')
    t = MessageTemplate(org_id=org.id, name=name.strip(), body=body.strip())
    db.session.add(t)
    db.session.commit()
    audit('template_create', t.name)
    return t


def update_template(org, tid, *, name, body):
    t = MessageTemplate.query.filter_by(id=tid, org_id=org.id).first()
    if not t:
        raise TemplateError('Template not found.')
    t.name = name.strip()
    t.body = body.strip()
    db.session.commit()
    return t


def delete_template(org, tid):
    t = MessageTemplate.query.filter_by(id=tid, org_id=org.id).first()
    if not t:
        raise TemplateError('Template not found.')
    db.session.delete(t)
    db.session.commit()
    audit('template_delete', t.name)


def list_templates(org):
    return (MessageTemplate.query.filter_by(org_id=org.id)
            .order_by(MessageTemplate.id.desc()).all())