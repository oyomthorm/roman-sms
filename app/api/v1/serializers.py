def iso(dt): return dt.isoformat().replace("+00:00", "Z") if dt else None

def user(u):
    return {"id": u.id, "email": u.email, "name": getattr(u, "name", "Admin"), "role": u.role}

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
        "recipient_count": getattr(c, "recipient_count", 0), "cost_credits": getattr(c, "cost_credits", 0)
    }

def paginated(items, next_cursor):
    return {"items": items, "next_cursor": next_cursor}
