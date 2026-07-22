@echo off
setlocal EnableExtensions EnableDelayedExpansion
title CHECK SYSTEM v3 - DEPLOY MT4
cd /d "%~dp0"

echo Deploying EA + Include files to ALL MetaTrader data folders...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\deploy_mt4.ps1"
if errorlevel 1 (
  echo.
  echo DEPLOY FAILED.
  pause
  exit /b 1
)

echo.
echo Open MetaEditor from MT4:
echo   File -^> Open Data Folder -^> MQL4\Experts\CHECK_SYSTEM_V3.mq4
echo Then press F7. Must be 0 errors.
echo.
pause
