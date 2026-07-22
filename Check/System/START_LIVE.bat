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

if exist "runtime\STOP_TRADING" del /f /q "runtime\STOP_TRADING" >nul 2>&1

echo Validating config...
%PY% tools\validate_config.py --config config\local\system.json
if errorlevel 1 (
  echo Config kluda.
  pause
  exit /b 1
)

echo.
echo Redeploying EA files...
call "%~dp0scripts\deploy_mt4.bat"
echo.
echo IMPORTANT:
echo  - EA BridgeRootPath = EMPTY ^(AUTO^)
echo  - Allow DLL imports = ON
echo  - AutoTrading = ON
echo  - Chart comment must show: CHECK V2 bridge=...
echo.
echo Starting checktrader...
%PY% -m checktrader --config config\local\system.json
pause
