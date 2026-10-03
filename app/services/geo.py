"""
District reference lookups.

Districts are seeded once and treated as immutable reference data. This
module is the only place that reads or groups them, so if the reference
list ever changes the change is in one file.
"""
from app.extensions import db
from app.models import District


REGION_ORDER = ['Central', 'Eastern', 'Northern', 'Western']


def list_active():
    return (District.query
            .filter_by(is_active=True)
            .order_by(District.name)
            .all())


def list_by_region(active_only=True):
    """
    Return [(region_name, [District, ...]), ...] in a stable region order.
    """
    q = District.query
    if active_only:
        q = q.filter_by(is_active=True)
    rows = q.order_by(District.region, District.name).all()

    grouped = {}
    for d in rows:
        grouped.setdefault(d.region, []).append(d)

    ordered = []
    for region in REGION_ORDER:
        if region in grouped:
            ordered.append((region, grouped[region]))
    # Any region not in REGION_ORDER goes at the end, alphabetically
    for region in sorted(k for k in grouped if k not in REGION_ORDER):
        ordered.append((region, grouped[region]))
    return ordered


def get(district_id):
    if not district_id:
        return None
    return db.session.get(District, district_id)


def find_by_name(name):
    """Case-insensitive lookup by exact name. Returns None if not found."""
    if not name:
        return None
    name = name.strip()
    if not name:
        return None
    return (District.query
            .filter(db.func.lower(District.name) == name.lower())
            .first())