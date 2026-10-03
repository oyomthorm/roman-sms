import re
from flask import current_app

PLACEHOLDER = re.compile(r'\{\{\s*(\w+)\s*\}\}')


def substitute(body, contact):
    def repl(m):
        key = m.group(1).lower()
        if key == 'name':
            return contact.name or ''
        if key == 'phone':
            return contact.phone or ''
        return m.group(0)
    return PLACEHOLDER.sub(repl, body)


def with_prefix(org, body):
    return f"{org.prefix}{body}"


from app.services.optout_links import optout_url

def append_optout(body, phone):
    url = optout_url(phone)
    if not url:
        return body
    return f"{body}\n\nOpt out: {url}"


def render(org, template_body, contact):
    body = with_prefix(org, substitute(template_body, contact))
    return append_optout(body, contact.phone)

def segments(body):
    size = current_app.config.get('SMS_SEGMENT_CHARS', 160)
    return max(1, -(-len(body) // size))