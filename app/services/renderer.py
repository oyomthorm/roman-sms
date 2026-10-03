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


def render(org, template_body, contact):
    """
    Render a message for one recipient.

    The result is the brand prefix plus the substituted body. No
    opt-out link is appended — see ADR-017. Recipients opt out via
    the public landing page, or the associate marks them manually.
    """
    return with_prefix(org, substitute(template_body, contact))


def segments(body):
    size = current_app.config.get('SMS_SEGMENT_CHARS', 160)
    return max(1, -(-len(body) // size))