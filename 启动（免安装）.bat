@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Mine Restoration Suitability Evaluation System V1.0 (portable)
set PORT=5000
set RT=%~dp0portable_runtime
set PY=%RT%\python.exe

echo.
echo ============================================================
echo   Mine Restoration Suitability Evaluation System  V1.0
echo   Portable edition - no Python installation required
echo ============================================================
echo.

if not exist "%PY%" (
  echo [ERROR] The bundled runtime was not found:
  echo         %PY%
  echo         Please unzip the WHOLE package again and keep the folder
  echo         structure unchanged, then double-click this file.
  echo.
  pause
  exit /b 1
)

REM ---- If the service is already running, just open the browser ----
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo [INFO] The service is already running on port %PORT%.
  echo        Opening the browser ...
  start "" "http://127.0.0.1:%PORT%"
  timeout /t 2 /nobreak >nul 2>&1
  exit /b 0
)

echo [1/3] Checking the bundled runtime ...
"%PY%" -c "import flask, flask_login, flask_wtf, flask_sqlalchemy, numpy, openpyxl, docx" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] The bundled runtime is incomplete. Please unzip the package again.
  echo.
  pause
  exit /b 1
)
echo       OK

echo [2/3] Preparing demo data ...
echo.
"%PY%" "%RT%\_start.py" seed_demo.py
if errorlevel 1 (
  echo.
  echo [ERROR] Failed to prepare demo data. See the message above.
  echo.
  pause
  exit /b 1
)

echo.
echo [3/3] Starting server on port %PORT% ...
echo   The browser will open automatically in a moment.
echo   If it does not, open this address manually:
echo       http://127.0.0.1:%PORT%
echo   Demo account: admin / admin123
echo   To stop the system: press Ctrl+C, or just close this window.
echo.
echo ============================================================
echo.

"%PY%" "%RT%\_start.py" run.py --port %PORT%

echo.
echo Server stopped.
pause
