@echo off
setlocal EnableExtensions
title SYSTEM - lejuplade uzreiz
color 0A
set "EXIT_CODE=1"

echo.
echo  ============================================================
echo   SYSTEM - AUTOMATISKA LEJUPIELADE UN UZSTADISANA
echo  ============================================================
echo.
echo   Meprice: C:\SYSTEM
echo   Avots:   GitHub main
echo.
echo   Uzgaidiet... (1-3 minutes)
echo.

where powershell >nul 2>&1
if errorlevel 1 (
  echo [KLUDA] PowerShell nav atrasts.
  goto :fail
)

set "SCRIPT_URL=https://raw.githubusercontent.com/voldis1994/VS_READER_ENGINE_V2/main/SYSTEM/scripts/install_windows.ps1"
set "SCRIPT_FILE=%TEMP%\system_install_%RANDOM%.ps1"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ^
   Write-Host 'Lejupielade instalacijas skriptu...' -ForegroundColor Cyan; ^
   Invoke-WebRequest -Uri '%SCRIPT_URL%' -OutFile '%SCRIPT_FILE%' -UseBasicParsing; ^
   if (-not (Test-Path '%SCRIPT_FILE%')) { throw 'Neizdevas lejupieladet skriptu' }"

if errorlevel 1 goto :fail

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_FILE%" -InstallPath "C:\SYSTEM" -SkipTests
set "EXIT_CODE=%ERRORLEVEL%"

del /f /q "%SCRIPT_FILE%" >nul 2>&1

echo.
if %EXIT_CODE% neq 0 (
  echo  [KLUDA] Uzstadisana neizdevas. Exit code: %EXIT_CODE%
  goto :fail
)

echo  ============================================================
echo   GATAVS! Projekts: C:\SYSTEM
echo  ============================================================
echo.
echo   Palaid live:  C:\SYSTEM\PALAID.bat
echo.
goto :end

:fail
echo.
echo  Nepieciesams: Python 3.11+ no https://www.python.org/downloads/
echo  Instalejiet ar "Add Python to PATH"
echo.

:end
pause
exit /b %EXIT_CODE%
