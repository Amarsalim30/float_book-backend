# backend

A project created with FastAPI CLI.

## Quick Start

### Start the development server

```bash
uv run fastapi dev
```

Visit http://localhost:8000

### Deploy to FastAPI Cloud

Sign up and log in at https://fastapicloud.com, then deploy with:

```bash
uv run fastapi deploy
```

## Project Structure

- `main.py` - Your FastAPI application
- `pyproject.toml` - Project dependencies

## Backups

Nightly database backups and restores live in `scripts/` and write to `backend/backups/`.

- **Backup:** `python scripts/backup_db.py` — dumps Postgres via `pg_dump -Fc` (or copies the file for SQLite), keeps the last 14.
- **Restore:** `python scripts/restore_db.py [file.dump]` — replaces the current DB with a backup. Defaults to the newest backup. Uses `--dry-run` to preview the command first.
- **Schedule (Windows workstation):** run `scripts/install_backup_schedule.bat` once as Administrator. Creates two tasks: **on logon** (fires every time you sign in — the workstation powers off in the evening, so a fixed 02:00 run would never fire) plus a **daily 11:00** safety-net snapshot.
- **Linux/cloud cron:** `0 2 * * * cd /path/to/backend && /path/to/.venv/bin/python scripts/backup_db.py`

Both scripts read `DATABASE_URL` from the same `.env` the app uses, so they always target the right database. Backups are gitignored.

## Learn More

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [FastAPI Cloud](https://fastapicloud.com)
