@echo off
setlocal EnableExtensions
title CHECK SYSTEM v2 - START LIVE
cd /d "%~dp0"

if not exist "config\local\system.json" (
  echo Vispirms palaid SETUP_ALL.bat
  pause
  exit /b 1
)

set "PY=python"
where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3.12 -c "import sys" >nul 2>&1
  if %ERRORLEVEL%==0 set "PY=py -3.12"
)

if exist "runtime\STOP_TRADING" (
  echo Kill switch AKTIVS: runtime\STOP_TRADING
  echo Izdzes failu, lai tirgotu, vai palaid STOP.bat tikai kad vajag apturet.
  pause
  exit /b 1
)

echo Validating config...
%PY% tools\validate_config.py --config config\local\system.json
if errorlevel 1 (
  echo Config kluda - ieraksti allowed_account_numbers.
  notepad config\local\system.json
  pause
  exit /b 1
)

echo.
echo Starting checktrader...
echo BridgeRootPath EA: %CD%
echo.
%PY% -m checktrader --config config\local\system.json
pause
