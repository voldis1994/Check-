@echo off
setlocal EnableExtensions
title CHECK SYSTEM — build CHECK_SYSTEM.exe
cd /d "%~dp0"

echo.
echo  Building CHECK_SYSTEM.exe  (PyInstaller, Windows)
echo  Output: dist\CHECK_SYSTEM\CHECK_SYSTEM.exe
echo.

python -c "import PyInstaller" 1>nul 2>nul
if errorlevel 1 (
  echo Installing PyInstaller...
  python -m pip install --upgrade pyinstaller
  if errorlevel 1 (
    echo Failed to install PyInstaller.
    pause
    exit /b 1
  )
)

python -c "import tkinter" 1>nul 2>nul
if errorlevel 1 (
  echo Tkinter missing. Install official Python 3.12+ for Windows with tcl/tk.
  pause
  exit /b 1
)

if exist "build" rmdir /S /Q "build"
if exist "dist\CHECK_SYSTEM" rmdir /S /Q "dist\CHECK_SYSTEM"

python -m PyInstaller --noconfirm --clean "CHECK_SYSTEM.spec"
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

REM Keep the exe next to a usable System tree: copy config example + point users to run from System root.
if not exist "dist\CHECK_SYSTEM\config" mkdir "dist\CHECK_SYSTEM\config"
copy /Y "config\system.example.json" "dist\CHECK_SYSTEM\config\system.example.json" >nul
if exist "config\system.json" copy /Y "config\system.json" "dist\CHECK_SYSTEM\config\system.json" >nul
if exist "config\platform.example.json" copy /Y "config\platform.example.json" "dist\CHECK_SYSTEM\config\platform.example.json" >nul
if exist "config\platform.json" copy /Y "config\platform.json" "dist\CHECK_SYSTEM\config\platform.json" >nul
if not exist "dist\CHECK_SYSTEM\clients" mkdir "dist\CHECK_SYSTEM\clients"

echo.
echo  DONE.
echo  Run:  dist\CHECK_SYSTEM\CHECK_SYSTEM.exe
echo  Or double-click START_CHECK_SYSTEM.bat  (dev / no build needed)
echo.
pause
