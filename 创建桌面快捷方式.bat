@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Create Desktop Shortcut

echo.
echo ============================================================
echo   Create a desktop shortcut for the system
echo ============================================================
echo.

python "工具\创建桌面快捷方式.py"
if errorlevel 1 (
  echo.
  echo [ERROR] Failed to create the shortcut.
  echo         Please make sure Python 3 is installed.
  echo.
  pause
  exit /b 1
)

echo.
pause
