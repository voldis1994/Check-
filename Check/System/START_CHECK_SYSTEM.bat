@echo off
setlocal EnableExtensions
title CHECK COMMAND
cd /d "%~dp0"

set "PYTHONPATH=%CD%\src;%CD%\tools;%PYTHONPATH%"

if not exist "config\system.json" (
  if exist "config\system.example.json" (
    copy /Y "config\system.example.json" "config\system.json" >nul
    echo Created config\system.json from example.
  )
)

REM Prefer frozen exe if present
if exist "dist\CHECK_SYSTEM\CHECK_SYSTEM.exe" (
  start "" "dist\CHECK_SYSTEM\CHECK_SYSTEM.exe"
  exit /b 0
)
if exist "CHECK_SYSTEM.exe" (
  start "" "CHECK_SYSTEM.exe"
  exit /b 0
)

python "tools\sync_system_config.py" --config "config\system.json" --example "config\system.example.json"
if errorlevel 1 (
  echo Config sync failed.
  pause
  exit /b 1
)

python -c "import tkinter" 1>nul 2>nul
if errorlevel 1 (
  echo Tkinter missing. Install official Python 3.12+ for Windows with tcl/tk.
  pause
  exit /b 1
)

python "tools\check_app.py"
if errorlevel 1 (
  echo.
  echo CHECK COMMAND exited with an error.
  pause
  exit /b 1
)
