@echo off
setlocal EnableExtensions
title BUILD CHECK.exe
cd /d "%~dp0"

python -m pip install --upgrade pyinstaller >nul
if exist "build" rmdir /S /Q "build"
if exist "dist\CHECK" rmdir /S /Q "dist\CHECK"

python -m PyInstaller --noconfirm --clean "CHECK.spec"
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

if not exist "dist\CHECK\config" mkdir "dist\CHECK\config"
copy /Y "config\defaults.json" "dist\CHECK\config\defaults.json" >nul
if exist "config\settings.json" copy /Y "config\settings.json" "dist\CHECK\config\settings.json" >nul
if not exist "dist\CHECK\clients" mkdir "dist\CHECK\clients"
if not exist "dist\CHECK\mt4" mkdir "dist\CHECK\mt4"
copy /Y "mt4\CHECK.mq4" "dist\CHECK\mt4\CHECK.mq4" >nul
copy /Y "START.bat" "dist\CHECK\START.bat" >nul

echo.
echo DONE: dist\CHECK\CHECK.exe
pause
