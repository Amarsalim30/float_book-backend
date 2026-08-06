@echo off
rem ============================================================
rem FPesa FastAPI Backend Windows Service Runner
rem ============================================================
cd /d "%~dp0"

rem Create logs directory if missing
if not exist "logs" mkdir logs

rem Activate virtual environment
call .venv\Scripts\activate.bat

rem Apply database migrations automatically at startup
call alembic upgrade head

rem Launch FastAPI server on port 8000
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
