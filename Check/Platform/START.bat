@echo off
setlocal EnableExtensions
title CHECK Platform
cd /d "%~dp0"

if not exist "clients" mkdir "clients"
if not exist "runtime" mkdir "runtime"
if not exist "config\settings.json" (
  copy /Y "config\defaults.json" "config\settings.json" >nul
)

if exist "dist\CHECK\CHECK.exe" (
  start "" "dist\CHECK\CHECK.exe"
  exit /b 0
)
if exist "CHECK.exe" (
  start "" "CHECK.exe"
  exit /b 0
)

set "PYTHONPATH=%CD%;%PYTHONPATH%"
python -c "import tkinter" 1>nul 2>nul
if errorlevel 1 (
  echo Install Python 3.12+ with Tcl/Tk.
  pause
  exit /b 1
)
python -m app.main
if errorlevel 1 (
  echo CHECK exited with error.
  pause
  exit /b 1
)
