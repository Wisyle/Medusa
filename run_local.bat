@echo off
REM Local development runner for TGL MEDUSA on Windows
REM Sets up proper Python path and runs the application

set PYTHONPATH=%cd%
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
