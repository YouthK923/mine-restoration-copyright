@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Mine Restoration Suitability Evaluation System V1.0

echo.
echo ============================================================
echo   Mine Restoration Suitability Evaluation System  V1.0
echo ============================================================
echo.

echo [1/2] Loading demo data ...
echo.
python seed_demo.py
if errorlevel 1 (
  echo.
  echo [ERROR] Failed to load demo data.
  echo         Please make sure Python is installed and run:
  echo             pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

echo.
echo [2/2] Starting server ...
echo.
echo   Open in browser :  http://127.0.0.1:5000
echo   Account         :  admin / admin123
echo   Stop            :  press Ctrl+C in this window
echo.
echo ============================================================
echo.

python run.py

echo.
echo Server stopped.
pause
