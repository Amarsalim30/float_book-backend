@echo off
rem ============================================================
rem FPesa Workstation Setup Script (One-Click Installer)
rem ============================================================
cd /d "%~dp0"

echo ============================================================
echo Installing FPesa Backend on Workstation...
echo ============================================================

rem 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH!
    echo Please install Python 3.11 or higher from https://python.org
    pause
    exit /b 1
)

rem 2. Create virtual environment if missing
if not exist ".venv" (
    echo Creating Python virtual environment...
    python -m venv .venv
)

rem 3. Activate virtual environment and install dependencies
echo Installing Python dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

rem 4. Copy .env.example to .env if .env doesn't exist
if not exist ".env" (
    echo Creating default .env config...
    copy .env.example .env
)

rem 5. Create logs directory
if not exist "logs" mkdir logs

rem 6. Run database migrations
echo Initializing database schema...
call alembic upgrade head

echo ============================================================
echo Setup complete! You can now run run_service.bat or setup NSSM.
echo ============================================================
pause
