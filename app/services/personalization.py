"""
Personalized campaign sends.

Schools (and later SACCOs, pharmacies, landlords) need per-recipient
messages: fee reminders with pupil name, parent name, fee balance,
due date, bursar contact; meeting reminders with parent name, meeting
time, headteacher contact.

The campaign pipeline already stores per-row rendered bodies on
MessageLog.body (see services/campaigns.py). The only thing missing is
a way to accept recipients that are NOT Contact rows and to render the
template body against a dict of per-row variables rather than a Contact.

This module provides that:
  - parse_csv(file_stream)   -> (columns, rows, issues)
  - validate_template(body, columns) -> list[str]
  - render_row(org, template_body, row) -> str
  - preview(org, template_body, rows, limit=3) -> dict

Rows are dicts of the shape: {'phone': '<canonical 256...>', 'vars': {col: value, ...}}
"""
import csv
import io

from app.services.phones import normalize_ug, describe
from app.services.renderer import (
    render_personalized, segments, PLACEHOLDER,
)


# Same alias list as services/contacts.import_csv — keep them in sync
# if either is changed.
PHONE_COLUMN_ALIASES = [
    'phone', 'number', 'mobile', 'msisdn',
    'phone_number', 'phone number',
    'mobile_number', 'mobile number',
    'telephone', 'tel', 'contact_phone',
]

MAX_ROWS = 500


class PersonalizationError(Exception):
    """Raised when a personalized campaign can't be built from its inputs."""
    pass


def parse_csv(file_stream):
    """
    Parse a personalized-send CSV.

    Returns (columns, rows, issues):
      columns  -- list of header names (original casing, in file order)
      rows     -- list of {'phone': canonical, 'vars': {col_lower: value, ...}}
      issues   -- list of {'row_num': int, 'status': str,
                           'reason': str, 'raw_phone': str}

    Raises PersonalizationError if the file is unreadable, has no phone
    column, or exceeds MAX_ROWS.
    """
    text = file_stream.read()
    if isinstance(text, bytes):
        text = text.decode('utf-8-sig', errors='ignore')

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise PersonalizationError(
            'CSV is empty or has no header row.')

    original_fields = list(reader.fieldnames)
    lower_names = [(f or '').strip().lower() for f in original_fields]

    phone_key = None
    for candidate in PHONE_COLUMN_ALIASES:
        if candidate in lower_names:
            phone_key = original_fields[lower_names.index(candidate)]
            break

    if phone_key is None:
        raise PersonalizationError(
            'CSV is missing a phone number column. '
            'Accepted headers: ' + ', '.join(PHONE_COLUMN_ALIASES) + '.')

    # Columns exposed as template variables: everything except the phone
    # column. Lower-cased for template lookup ({{PupilName}} and
    # {{pupilname}} are the same variable; documented in the UI).
    variable_columns = [
        f for f in original_fields if f != phone_key
    ]
    variable_keys_lower = [f.strip().lower() for f in variable_columns]

    rows = []
    issues = []
    seen_phones = set()

    for row_num, raw_row in enumerate(reader, start=2):
        if row_num - 1 > MAX_ROWS + 1:
            # +1 to account for header row counted by start=2 offset.
            issues.append({
                'row_num': row_num,
                'status': 'skipped',
                'reason': f'row limit exceeded (max {MAX_ROWS})',
                'raw_phone': '',
            })
            continue

        raw_phone = (raw_row.get(phone_key) or '').strip()
        canonical, reason = describe(raw_phone)

        if not canonical:
            issues.append({
                'row_num': row_num,
                'status': 'invalid',
                'reason': reason or 'invalid',
                'raw_phone': raw_phone[:60],
            })
            continue

        if canonical in seen_phones:
            issues.append({
                'row_num': row_num,
                'status': 'duplicate',
                'reason': 'duplicate phone in file',
                'raw_phone': raw_phone[:60],
            })
            continue
        seen_phones.add(canonical)

        variables = {}
        for orig_header, lower_key in zip(variable_columns, variable_keys_lower):
            value = raw_row.get(orig_header)
            if value is None:
                value = ''
            variables[lower_key] = str(value).strip()

        rows.append({'phone': canonical, 'vars': variables})

    if not rows:
        raise PersonalizationError(
            'No valid rows in the CSV. '
            f'({len(issues)} row(s) were skipped.)')

    return original_fields, rows, issues


def validate_template(template_body, columns):
    """
    Check that every {{var}} in the template body refers to a known column
    (or is one of the built-in pass-throughs).

    Returns a list of error strings. Empty list means valid.
    """
    known = {c.strip().lower() for c in columns}
    refs = PLACEHOLDER.findall(template_body or '')
    errors = []
    for ref in refs:
        key = ref.lower()
        if key not in known:
            errors.append(
                f'Template references {{{{{ref}}}}} but the CSV has no '
                f'column named "{ref}".')
    # Deduplicate, preserve order.
    seen = set()
    out = []
    for e in errors:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


def render_row(org, template_body, row):
    """Render one row's message: brand prefix + substituted template."""
    return render_personalized(org, template_body, row['vars'])


def preview(org, template_body, rows, limit=3):
    """
    Build a preview response for the web form.

    Returns a dict with everything the client needs:
      columns         -- variable column names (no phone)
      row_count       -- total eligible rows
      total_segments  -- sum of per-row segment counts
      preview         -- up to `limit` rows with rendered body + segments
      issues          -- the parse issues (may be empty)
      errors          -- template errors (may be empty)

    Note: does NOT hit the DB and does NOT debit the wallet. This is
    the shape the /campaigns/personalized/preview endpoint returns.
    """
    columns = sorted({k for r in rows for k in r['vars'].keys()})
    errors = validate_template(template_body, columns)

    samples = []
    total_segments = 0
    for row in rows:
        body = render_row(org, template_body, row)
        segs = segments(body)
        total_segments += segs
        if len(samples) < limit:
            samples.append({
                'phone': row['phone'],
                'body': body,
                'segments': segs,
            })

    return {
        'columns': columns,
        'row_count': len(rows),
        'total_segments': total_segments,
        'preview': samples,
        'errors': errors,
    }