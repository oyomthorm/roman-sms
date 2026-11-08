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


def substitute_vars(body, variables):
    """
    Substitute {{key}} placeholders from a dict of variables.

    Unknown keys are left verbatim (same behaviour as substitute()).
    Used by the personalized campaign path; substitute() stays as the
    Contact-based path for regular campaigns.
    """
    def repl(m):
        key = m.group(1).lower()
        if key in variables:
            return '' if variables[key] is None else str(variables[key])
        return m.group(0)
    return PLACEHOLDER.sub(repl, body)


def render_personalized(org, template_body, variables):
    """
    Render a personalized message for one recipient: brand prefix +
    substituted template body.

    The result is what gets stored on MessageLog.body — same shape as
    render() produces for a Contact, just with dict-based substitution.
    """
    return with_prefix(org, substitute_vars(template_body, variables))

def segments(body):
    size = current_app.config.get('SMS_SEGMENT_CHARS', 160)
    return max(1, -(-len(body) // size))