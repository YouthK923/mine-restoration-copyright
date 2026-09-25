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
set PY=python
where python >nul 2>&1
if errorlevel 1 (
  if exist "%USERPROFILE%\anaconda3\python.exe" set PY=%USERPROFILE%\anaconda3\python.exe
  if exist "D:\Anaconda3\python.exe" set PY=D:\Anaconda3\python.exe
  if exist "C:\ProgramData\Anaconda3\python.exe" set PY=C:\ProgramData\Anaconda3\python.exe
)

REM ---- Prepare demo data (idempotent; never deletes your own data) ----
echo [1/2] Preparing demo data ...
echo.
%PY% seed_demo.py
if errorlevel 1 (
  echo.
  echo [ERROR] Failed to prepare demo data.
  echo         Please make sure Python is installed, then run:
  echo             pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

REM ---- Start the server (the browser opens automatically) ----
echo.
echo [2/2] Starting server on port %PORT% ...
echo   The browser will open automatically in a moment.
echo   To stop the system: press Ctrl+C, or just close this window.
echo.
echo ============================================================
echo.

%PY% run.py --port %PORT%

echo.
echo Server stopped.
pause
