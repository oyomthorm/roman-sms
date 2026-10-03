"""
One-off price update — 2026-10-02.

Raises retail rate by UGX 5 per SMS on all four tiers. Existing
invoices are unaffected (they snapshot their amount at creation);
new invoices use the new prices.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models import Plan


NEW_PRICES = {
    'Starter': 50_000,
    'Growth': 450_000,
    'Business': 2_000_000,
    'Scale': 7_000_000,
}


def main():
    app = create_app()
    with app.app_context():
        changed = 0
        for name, new_price in NEW_PRICES.items():
            p = Plan.query.filter_by(name=name).first()
            if not p:
                print(f'[skip] {name} not found')
                continue
            if float(p.price) == float(new_price):
                print(f'[skip] {name} already at {new_price}')
                continue
            old = float(p.price)
            p.price = new_price
            changed += 1
            print(f'[update] {name}: {old:,.0f} → {new_price:,.0f}')
        db.session.commit()
        print(f'Done. {changed} plan(s) updated.')


if __name__ == '__main__':
    main()