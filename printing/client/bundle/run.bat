@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [printer-client] Python is not installed or not on PATH.
    echo Install Python 3.9+ from https://python.org and try again.
    pause
    exit /b 1
)

if not exist .env (
    echo [printer-client] No .env file found. Copy .env.sample to .env
    echo and fill in your Eolymp credentials and printer name.
    pause
    exit /b 1
)

if not exist .deps (
    echo [printer-client] First run: installing Python dependencies into .deps\ ...
    python -m pip install --target .deps -r requirements.txt
    if errorlevel 1 (
        echo [printer-client] pip install failed.
        pause
        exit /b 1
    )
)

set PYTHONPATH=%cd%\.deps;%PYTHONPATH%
python printer.py
set rc=%errorlevel%
if not "%rc%"=="0" pause
exit /b %rc%
