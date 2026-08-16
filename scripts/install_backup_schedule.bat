@echo off
rem ============================================================
rem Schedule Floatbook database backups on Windows.
rem
rem The workstation powers off in the evening, so a fixed 02:00
rem nightly run would never fire. Instead we create two tasks:
rem
rem   1. On logon   - runs scripts\backup_db.py every time you sign in
rem                  (machine is on + user active = guaranteed to run)
rem   2. Daily 11:00 - mid-day safety-net snapshot while the machine
rem                  is definitely powered on during working hours
rem
rem Retention (--keep 14) handles multiple snapshots per day.
rem Run this once from backend\scripts\ as Administrator.
rem ============================================================
cd /d "%~dp0..\"

set "PY=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: venv python not found at %PY%
  echo Create it first: python -m venv .venv
  exit /b 1
)

rem Task 1: on every user logon
set "CMD1=\"%PY%\" \"%~dp0backup_db.py\" --keep 14"
schtasks /create /tn "Floatbook DB Backup" /tr "%CMD1%" /sc onlogon /f
if %errorlevel% neq 0 (
  echo ERROR: failed to create the logon task. Re-run as Administrator.
  exit /b %errorlevel%
)

rem Task 2: mid-day daily snapshot (safety net)
set "CMD2=\"%PY%\" \"%~dp0backup_db.py\" --keep 14"
schtasks /create /tn "Floatbook DB Backup Daily" /tr "%CMD2%" /sc daily /st 11:00 /f
if %errorlevel% neq 0 (
  echo ERROR: failed to create the daily task. Re-run as Administrator.
  exit /b %errorlevel%
)

echo Scheduled: on-logon + daily 11:00 -> %~dp0..\backups\
echo Verify with: schtasks /query /tn "Floatbook DB Backup"
echo               schtasks /query /tn "Floatbook DB Backup Daily"
