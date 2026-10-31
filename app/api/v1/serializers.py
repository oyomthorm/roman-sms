def iso(dt): return dt.isoformat().replace("+00:00", "Z") if dt else None

def user(u):
    return {
        "id": u.id,
        "email": u.email,
        "name": getattr(u, "full_name", None) or "Admin",
        "role": u.role,
    }

def org(o):
    if o is None:
        return {"id": None, "name": "Unknown", "brand_prefix": ""}
    return {"id": o.id, "name": o.name, "brand_prefix": getattr(o, "brand_name", "")}

def wallet(balance, rate_ugx, value_ugx):
    return {"balance": balance, "rate_ugx": rate_ugx, "value_ugx": value_ugx}

def contact(c):
    return {
        "id": c.id, "phone": c.phone, "name": getattr(c, "name", ""), 
        "group_id": c.group_id, "district_id": getattr(c, "district_id", None), 
        "opted_out": getattr(c, "opted_out", False), "created_at": iso(c.created_at)
    }

def campaign(c):
    return {
        "id": c.id, "name": c.name, "status": c.status, "created_at": iso(c.created_at),
        "recipient_count": c.total, "cost_credits": c.credits_debited
    }

def paginated(items, next_cursor):
    return {"items": items, "next_cursor": next_cursor}

def group(g, contact_count=None):
    return {
        "id": g.id,
        "name": g.name,
        "description": getattr(g, "description", None),
        "contact_count": contact_count,
        "created_at": iso(g.created_at),
        "updated_at": iso(getattr(g, "updated_at", None)),
    }