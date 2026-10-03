"""
Backfill PoolContact.group_name from the source Contact.

Run once after adding the group_name column to pool_contact.

    python scripts/backfill_pool_groups.py

Idempotent — safe to re-run. Only updates rows where group_name is
currently null and the source contact has a group.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models import PoolContact, Contact


def main():
    app = create_app()
    with app.app_context():
        updated = 0
        scanned = 0

        for pc in PoolContact.query.all():
            scanned += 1
            if not pc.source_contact_id:
                continue
            c = db.session.get(Contact, pc.source_contact_id)
            if c and c.group and pc.group_name != c.group.name:
                pc.group_name = c.group.name
                updated += 1

        db.session.commit()
        print(f'Scanned {scanned} pool contacts. Updated {updated}.')


if __name__ == '__main__':
    main()