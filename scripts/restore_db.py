"""Restore a Floatbook backup created by scripts/backup_db.py.

Usage (from the backend/ directory):
    python scripts/restore_db.py [path/to/floatbook-<stamp>.dump]

If no path is given, the most recent backup in the backups/ directory is used.

WARNING: This DESTROYS the current database contents and replaces them with
the backup. For Postgres, the target database must already exist (created via
`createdb`); objects inside it are dropped and recreated from the archive.
"""
import argparse
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
    """Convert the SQLAlchemy URL to a libpq URL that pg_restore accepts."""
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def _restore_postgres(url, backup, pg_restore, dry_run=False) -> None:
    libpq = _pg_url(url)
    cmd = [
        pg_restore,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "-d", libpq,
        str(backup),
    ]
    if dry_run:
        print("Would run:", " ".join(cmd))
        return
    subprocess.run(cmd, check=True)


def _restore_sqlite(url, backup) -> None:
    db_path = Path(url.database)
    if not db_path.is_absolute():
        db_path = BACKEND_DIR / db_path
    if db_path.exists():
        db_path.unlink()
    shutil.copy2(backup, db_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", nargs="?", type=Path, help="backup file (default: newest in backups/)")
    parser.add_argument("--dry-run", action="store_true", help="print the restore command without running it")
    args = parser.parse_args()

    url = make_url(get_settings().DATABASE_URL)
    is_pg = url.get_backend_name().startswith("postgres")

    if args.backup is None:
        backup_dir = BACKEND_DIR / "backups"
        candidates = sorted(backup_dir.glob("floatbook-*.*"))
        if not candidates:
            sys.exit(f"No backups found in {backup_dir}")
        args.backup = candidates[-1]

    if not args.backup.exists():
        sys.exit(f"Backup file not found: {args.backup}")

    if is_pg:
        pg_restore = shutil.which("pg_restore")
        if not pg_restore:
            sys.exit("pg_restore not found on PATH. Install the PostgreSQL client tools.")
        _restore_postgres(url, args.backup, pg_restore, dry_run=args.dry_run)
    else:
        if args.dry_run:
            print(f"Would restore {args.backup} over the SQLite database {url.database}")
            return
        _restore_sqlite(url, args.backup)

    print(f"Restored {args.backup} into the {url.get_backend_name()} database.")


if __name__ == "__main__":
    main()
