"""Database backup with rotation.

    0 3 * * * cd /opt/roman-sms && ./venv/bin/python scripts/backup.py

Writes a gzip of the database to BACKUP_DIR. Rotates to KEEP most recent.
For Postgres, uses pg_dump; for SQLite, copies the file.
"""
import gzip
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

from app import create_app


def _backup_sqlite(db_path, out_path):
    with open(db_path, 'rb') as src, gzip.open(out_path, 'wb') as dst:
        shutil.copyfileobj(src, dst)


def _backup_postgres(dsn, out_path):
    # Requires pg_dump on PATH. DSN is the full postgresql:// URL.
    with gzip.open(out_path, 'wb') as dst:
        subprocess.run(['pg_dump', dsn], check=True, stdout=dst)


def main():
    app = create_app()
    backup_dir = Path(app.config.get('BACKUP_DIR', 'backups'))
    keep = int(app.config.get('BACKUP_KEEP', 30))
    backup_dir.mkdir(exist_ok=True, parents=True)

    stamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    dsn = app.config['SQLALCHEMY_DATABASE_URI']

    if dsn.startswith('sqlite'):
        # sqlite:///relative/path.db or sqlite:////absolute/path.db
        path = dsn.split('sqlite:///', 1)[-1]
        if not path or path == ':memory:':
            print('Refusing to back up an in-memory database.')
            return
        out = backup_dir / f'roman-{stamp}.db.gz'
        _backup_sqlite(path, out)
    elif dsn.startswith('postgresql'):
        out = backup_dir / f'roman-{stamp}.sql.gz'
        _backup_postgres(dsn, out)
    else:
        print(f'Unsupported database: {dsn}')
        sys.exit(1)

    print(f'Wrote {out}')

    # Rotate
    files = sorted(backup_dir.glob('roman-*'), reverse=True)
    for old in files[keep:]:
        old.unlink()
        print(f'Removed {old}')


if __name__ == '__main__':
    main()