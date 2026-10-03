"""
Populate the district reference table.

Idempotent — safe to re-run. Existing districts are not modified; only
missing ones are added. Deactivate rather than delete a district that
should no longer be selectable, so historical contacts keep their link.

Run after `flask db upgrade` and `scripts/seed.py`:
    python scripts/seed_districts.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models import District


DISTRICTS = [
    # Central
    ('Kampala', 'Central'), ('Wakiso', 'Central'), ('Mukono', 'Central'),
    ('Mpigi', 'Central'), ('Luweero', 'Central'), ('Mityana', 'Central'),
    ('Nakaseke', 'Central'), ('Nakasongola', 'Central'), ('Kayunga', 'Central'),
    ('Buikwe', 'Central'), ('Buvuma', 'Central'), ('Gomba', 'Central'),
    ('Butambala', 'Central'), ('Kalangala', 'Central'), ('Kyankwanzi', 'Central'),
    ('Kiboga', 'Central'), ('Masaka', 'Central'), ('Bukomansimbi', 'Central'),
    ('Kalungu', 'Central'), ('Lwengo', 'Central'), ('Lyantonde', 'Central'),
    ('Rakai', 'Central'), ('Sembabule', 'Central'), ('Kyotera', 'Central'),
    ('Entebbe', 'Central'), ('Kira', 'Central'), ('Nansana', 'Central'),
    ('Makindye-Ssabagabo', 'Central'), ('Kiira', 'Central'),
    # Eastern
    ('Jinja', 'Eastern'), ('Iganga', 'Eastern'), ('Mayuge', 'Eastern'),
    ('Bugiri', 'Eastern'), ('Namayingo', 'Eastern'), ('Busia', 'Eastern'),
    ('Tororo', 'Eastern'), ('Butaleja', 'Eastern'), ('Manafwa', 'Eastern'),
    ('Mbale', 'Eastern'), ('Sironko', 'Eastern'), ('Bulambuli', 'Eastern'),
    ('Kapchorwa', 'Eastern'), ('Kween', 'Eastern'), ('Bukwo', 'Eastern'),
    ('Kamuli', 'Eastern'), ('Kaliro', 'Eastern'), ('Buyende', 'Eastern'),
    ('Luuka', 'Eastern'), ('Namutumba', 'Eastern'), ('Bududa', 'Eastern'),
    ('Budaka', 'Eastern'), ('Kibuku', 'Eastern'), ('Butebo', 'Eastern'),
    ('Pallisa', 'Eastern'), ('Kumi', 'Eastern'), ('Ngora', 'Eastern'),
    ('Serere', 'Eastern'), ('Soroti', 'Eastern'), ('Katakwi', 'Eastern'),
    ('Amuria', 'Eastern'), ('Kaberamaido', 'Eastern'), ('Kalaki', 'Eastern'),
    # Northern
    ('Gulu', 'Northern'), ('Amuru', 'Northern'), ('Nwoya', 'Northern'),
    ('Omoro', 'Northern'), ('Kitgum', 'Northern'), ('Lamwo', 'Northern'),
    ('Pader', 'Northern'), ('Agago', 'Northern'), ('Lira', 'Northern'),
    ('Dokolo', 'Northern'), ('Alebtong', 'Northern'), ('Amolatar', 'Northern'),
    ('Kole', 'Northern'), ('Oyam', 'Northern'), ('Apac', 'Northern'),
    ('Kwania', 'Northern'), ('Otuke', 'Northern'), ('Arua', 'Northern'),
    ('Nebbi', 'Northern'), ('Zombo', 'Northern'), ('Arua City', 'Northern'),
    ('Maracha', 'Northern'), ('Koboko', 'Northern'), ('Yumbe', 'Northern'),
    ('Moyo', 'Northern'), ('Adjumani', 'Northern'), ('Obongi', 'Northern'),
    ('Madi Okollo', 'Northern'), ('Terego', 'Northern'), ('Pakwach', 'Northern'),
    ('Kotido', 'Northern'), ('Kaabong', 'Northern'), ('Abim', 'Northern'),
    ('Moroto', 'Northern'), ('Nakapiripirit', 'Northern'), ('Napak', 'Northern'),
    ('Amudat', 'Northern'), ('Karenga', 'Northern'),
    # Western
    ('Mbarara', 'Western'), ('Bushenyi', 'Western'), ('Sheema', 'Western'),
    ('Ntungamo', 'Western'), ('Isingiro', 'Western'), ('Kiruhura', 'Western'),
    ('Ibanda', 'Western'), ('Buhweju', 'Western'), ('Rubirizi', 'Western'),
    ('Rukungiri', 'Western'), ('Kanungu', 'Western'), ('Kabale', 'Western'),
    ('Kisoro', 'Western'), ('Kabale City', 'Western'), ('Kasese', 'Western'),
    ('Kasese City', 'Western'), ('Kamwenge', 'Western'), ('Kyenjojo', 'Western'),
    ('Kyegegwa', 'Western'), ('Kitagwenda', 'Western'), ('Bundibugyo', 'Western'),
    ('Ntoroko', 'Western'), ('Hoima', 'Western'), ('Kikuube', 'Western'),
    ('Masindi', 'Western'), ('Kiryandongo', 'Western'), ('Buliisa', 'Western'),
    ('Kagadi', 'Western'), ('Kakumiro', 'Western'), ('Kibaale', 'Western'),
    ('Mubende', 'Western'), ('Kassanda', 'Western'),
]


REGION_ORDER = ['Central', 'Eastern', 'Northern', 'Western']


def main():
    app = create_app()
    with app.app_context():
        added = 0
        existing = 0

        for name, region in DISTRICTS:
            row = District.query.filter_by(name=name).first()
            if row:
                existing += 1
                continue
            db.session.add(District(name=name, region=region))
            added += 1

        db.session.commit()

        total = District.query.count()
        print(f'Added {added}, already present {existing}. Total: {total}.')

        by_region = (db.session.query(District.region,
                                      db.func.count(District.id))
                     .group_by(District.region)
                     .order_by(District.region)
                     .all())
        for region, count in by_region:
            print(f'  {region}: {count}')

        # Sanity check.
        missing_regions = (set(r for r, _ in by_region)
                           - set(REGION_ORDER))
        if missing_regions:
            print(f'  WARNING: unexpected regions in DB: '
                  f'{", ".join(sorted(missing_regions))}')


if __name__ == '__main__':
    main()