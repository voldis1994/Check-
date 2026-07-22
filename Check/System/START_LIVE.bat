@echo off
setlocal EnableExtensions
title CHECK SYSTEM v2 - START LIVE
cd /d "%~dp0"

set "PY=python"
where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3.12 -c "import sys" >nul 2>&1
  if %ERRORLEVEL%==0 set "PY=py -3.12"
)

echo [1/4] Force AUTO config ^(symbol + ALL accounts^)...
%PY% tools\seed_local_config.py --root "%CD%"
if errorlevel 1 (
  echo Seed kluda.
  pause
  exit /b 1
)

if exist "runtime\STOP_TRADING" del /f /q "runtime\STOP_TRADING" >nul 2>&1

echo.
echo [2/4] Validate...
%PY% tools\validate_config.py --config config\local\system.json
if errorlevel 1 (
  echo Config kluda.
  pause
  exit /b 1
)

echo.
echo [3/4] Deploy EA to ALL MetaTrader folders...
call "%~dp0scripts\deploy_mt4.bat"

echo.
echo [4/4] Detected bridges/accounts:
%PY% tools\show_bridges.py --config config\local\system.json
if errorlevel 1 (
  echo.
  echo Nav bridge failu. Uzliec EA uz KATRA konta M1:
  echo   BridgeRootPath=TUKSS  Allow DLL imports=ON  AutoTrading=ON
  echo Tad MetaEditor F7 un START_LIVE.bat velreiz.
  pause
  exit /b 1
)

echo.
echo Starting checktrader — multi-account AUTO...
%PY% -m checktrader --config config\local\system.json
pause
