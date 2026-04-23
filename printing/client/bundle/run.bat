@echo off
setlocal
cd /d "%~dp0"

set PY=python\python.exe
if not exist "%PY%" (
    echo [printer-client] Bundled Python missing at %PY%.
    echo This bundle is broken; re-download from
    echo   https://github.com/ocpc-camp/eolymp-tools/releases
    pause
    exit /b 1
)

if not exist .env (
    echo [printer-client] No .env file found. Copy .env.sample to .env
    echo and fill in your Eolymp credentials and printer name, then run
    echo this script again.
    pause
    exit /b 1
)

"%PY%" printer.py
set rc=%errorlevel%
if not "%rc%"=="0" pause
exit /b %rc%
