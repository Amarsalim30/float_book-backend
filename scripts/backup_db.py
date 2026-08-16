"""Create a compressed, timestamped backup of the Floatbook database.

Works for both supported backends:
  * PostgreSQL  -> `pg_dump -Fc` (compressed custom-format archive)
  * SQLite      -> plain file copy

The database URL is read from the same .env the app uses, so this script
always backs up the database the app is actually running against.

Usage (from the backend/ directory):
    python scripts/backup_db.py [--keep N] [--backup-dir DIR]

Examples:
    python scripts/backup_db.py                # default: keep last 14
    python scripts/backup_db.py --keep 30

Linux cron equivalent (nightly 02:00):
    0 2 * * * cd /path/to/backend && /path/to/.venv/bin/python scripts/backup_db.py >> backups/backup.log 2>&1
"""
import argparse
import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import get_settings  # noqa: E402


def _pg_url(url) -> str:
    """Convert the SQLAlchemy URL to a libpq URL that pg_dump accepts."""
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def _backup_postgres(url, dest, pg_dump) -> None:
    libpq = _pg_url(url)
    cmd = [pg_dump, "-Fc", "--no-owner", "--no-privileges", "-f", str(dest), libpq]
    subprocess.run(cmd, check=True)


def _backup_sqlite(url, dest) -> None:
    db_path = Path(url.database)
    if not db_path.is_absolute():
        db_path = BACKEND_DIR / db_path
    if not db_path.exists():
        sys.exit(f"SQLite database not found: {db_path}")
    shutil.copy2(db_path, dest)


def _prune(backup_dir: Path, keep: int) -> None:
    backups = sorted(backup_dir.glob("floatbook-*.dump")) + sorted(
        backup_dir.glob("floatbook-*.db")
    )
    for old in backups[:-keep]:
        old.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", type=int, default=14, help="number of backups to retain (default 14)")
    parser.add_argument("--backup-dir", type=Path, default=BACKEND_DIR / "backups")
    args = parser.parse_args()

    url = make_url(get_settings().DATABASE_URL)
    args.backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    is_pg = url.get_backend_name().startswith("postgres")
    suffix = "dump" if is_pg else "db"
    dest = args.backup_dir / f"floatbook-{stamp}.{suffix}"

    if is_pg:
        pg_dump = shutil.which("pg_dump")
        if not pg_dump:
            sys.exit("pg_dump not found on PATH. Install the PostgreSQL client tools or add pg_dump to PATH.")
        _backup_postgres(url, dest, pg_dump)
    else:
        _backup_sqlite(url, dest)

    _prune(args.backup_dir, args.keep)
    print(f"Backup written: {dest}")
    print(f"Backups retained: {args.keep}")


if __name__ == "__main__":
    main()
