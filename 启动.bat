@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Mine Restoration Suitability Evaluation System V1.0
set PORT=5000

echo.
echo ============================================================
echo   Mine Restoration Suitability Evaluation System  V1.0
echo ============================================================
echo.

REM ---- If the service is already running, just open the browser ----
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo [INFO] The service is already running on port %PORT%.
  echo        Opening the browser ...
  start "" "http://127.0.0.1:%PORT%"
  timeout /t 2 /nobreak >nul 2>&1
  exit /b 0
)

REM ---- Locate Python ----
set PY=
where python >nul 2>&1 && set PY=python
if not defined PY (
  where py >nul 2>&1 && set PY=py -3
)
if not defined PY (
  for %%P in (
    "%USERPROFILE%\anaconda3\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
    "D:\Anaconda3\python.exe"
    "C:\ProgramData\Anaconda3\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
  ) do (
    if not defined PY if exist %%P set PY=%%P
  )
)
if not defined PY (
  echo [ERROR] Python was not found on this computer.
  echo.
  echo   This system needs Python 3.10+ ^(Anaconda is fine^).
  echo   Install from https://www.python.org/downloads/ , tick
  echo   "Add python.exe to PATH" during setup, then run this file again.
  echo.
  pause
  exit /b 1
)
echo [OK] Python: %PY%
echo.

REM ---- Check dependencies (install from the bundled wheels first) ----
set IMP=import flask, flask_login, flask_wtf, flask_sqlalchemy, numpy, openpyxl, docx
%PY% -c "%IMP%" >nul 2>&1
if errorlevel 1 (
  echo [1/3] Installing dependencies ...
  echo.
  if exist "offline_wheels" (
    echo       Trying the offline wheels in .\offline_wheels ...
    %PY% -m pip install --no-index --find-links offline_wheels -r requirements.txt
    echo.
  )
  %PY% -c "%IMP%" >nul 2>&1
  if errorlevel 1 (
    echo       Offline install did not finish it, trying the network ...
    %PY% -m pip install -r requirements.txt
    echo.
  )
  %PY% -c "%IMP%" >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Dependencies are still missing. Please run this line and read
    echo         the message it prints:
    echo             %PY% -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
  )
) else (
  echo [1/3] Dependencies: OK
)

REM ---- Prepare demo data (idempotent; never deletes your own data) ----
echo [2/3] Preparing demo data ...
echo.
%PY% seed_demo.py
if errorlevel 1 (
  echo.
  echo [ERROR] Failed to prepare demo data. See the message above.
  echo.
  pause
  exit /b 1
)

REM ---- Start the server (the browser opens automatically) ----
echo.
echo [3/3] Starting server on port %PORT% ...
echo   The browser will open automatically in a moment.
echo   Demo account: admin / admin123
echo   To stop the system: press Ctrl+C, or just close this window.
echo.
echo ============================================================
echo.

%PY% run.py --port %PORT%

echo.
echo Server stopped.
pause
