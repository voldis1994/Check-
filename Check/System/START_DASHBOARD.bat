@echo off
setlocal EnableExtensions
title CHECK SYSTEM - Ops Floor
cd /d "%~dp0"

set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

if not exist "config\system.json" (
  if exist "config\system.example.json" (
    copy /Y "config\system.example.json" "config\system.json" >nul
    echo Created config\system.json from example.
  )
)

REM Always refresh regimes/strategies from shipped example (keeps live/runtime settings).
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

python "tools\dashboard.py"
if errorlevel 1 (
  echo.
  echo Dashboard exited with an error.
  pause
  exit /b 1
)
