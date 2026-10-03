"""
Ugandan phone number normalization.

Canonical form: 256XXXXXXXXX (12 digits, no leading +).

Valid mobile prefixes after country code 256: 70-79.
  70, 74, 75 = Airtel
  76, 77, 78 = MTN
  71          = UTL (largely defunct but still routes some traffic)
  72          = Lycamobile
  73, 79      = Africell

Landlines (256 3X-6X) are rejected — SMS to a landline does not deliver,
and storing them silently pollutes the contact list.
"""
import re


# Canonical: 256 followed by 7 then 8 more digits.
# Covers 70-79 prefixes and validates the total length.
CANONICAL_RE = re.compile(r'^2567\d{8}$')


def normalize_ug(raw):
    """
    Return canonical 256XXXXXXXXX or None.

    Accepts:
      0700123456        -> 256700123456
      700123456         -> 256700123456
      256700123456      -> 256700123456
      +256700123456     -> 256700123456
      00256700123456    -> 256700123456
      (070) 012-3456    -> 256700123456
      070 012 3456      -> 256700123456
      0788-123-456      -> 256788123456
      "0700123456 "     -> 256700123456

    Rejects:
      0414123456        -> landline
      256414123456      -> landline
      12345678          -> too short
      +1 555 000 0000   -> not Ugandan
      ""                -> empty
    """
    if raw is None:
        return None
    digits = re.sub(r'\D', '', str(raw))
    if not digits:
        return None

    # Strip international dialing prefix 00
    if digits.startswith('00'):
        digits = digits[2:]

    # Already canonical: 256 + 9 digits
    if len(digits) == 12 and digits.startswith('256'):
        return digits if CANONICAL_RE.match(digits) else None

    # Local: 0 + 9 digits
    if len(digits) == 10 and digits.startswith('0'):
        candidate = '256' + digits[1:]
        return candidate if CANONICAL_RE.match(candidate) else None

    # Bare subscriber: 9 digits (no country code, no leading 0)
    if len(digits) == 9:
        candidate = '256' + digits
        return candidate if CANONICAL_RE.match(candidate) else None

    return None


def is_valid_ug(raw):
    return normalize_ug(raw) is not None


def describe(raw):
    """
    Return (canonical_or_None, reason_or_None).

    reason is a short human message suitable for the import preview.
    Only meaningful when canonical is None.
    """
    if raw is None or not str(raw).strip():
        return None, 'empty'

    digits = re.sub(r'\D', '', str(raw))
    if not digits:
        return None, 'no digits'

    d = digits
    if d.startswith('00'):
        d = d[2:]

    if len(d) == 12 and d.startswith('256'):
        if not CANONICAL_RE.match(d):
            return None, 'not a mobile number'
        return d, None

    if len(d) == 10 and d.startswith('0'):
        candidate = '256' + d[1:]
        if not CANONICAL_RE.match(candidate):
            return None, 'not a mobile number'
        return candidate, None

    if len(d) == 9:
        candidate = '256' + d
        if not CANONICAL_RE.match(candidate):
            return None, 'not a mobile number'
        return candidate, None

    if len(d) < 9:
        return None, f'too short ({len(d)} digits)'
    return None, f'invalid length ({len(d)} digits)'


import re


def parse_pasted_numbers(text, max_count=500):
    """
    Parse a blob of phone numbers.

    Accepts one per line, comma-separated, semicolon-separated, or
    whitespace-separated. Normalises each through normalize_ug,
    deduplicates, and skips anything invalid.

    Returns a list of canonical 256XXXXXXXXX strings, capped at
    max_count.
    """
    if not text:
        return []

    tokens = re.split(r'[\s,;]+', str(text).strip())

    seen = set()
    result = []
    for token in tokens:
        if not token:
            continue
        normalized = normalize_ug(token)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= max_count:
            break

    return result