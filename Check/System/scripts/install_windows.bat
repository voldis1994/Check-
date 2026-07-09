@echo off
setlocal
title SYSTEM - automatiska uzstadisana

echo.
echo ========================================
echo  SYSTEM - lejuplade un uzstadisana
echo ========================================
echo.

where powershell >nul 2>&1
if errorlevel 1 (
    echo Kluda: PowerShell nav atrasts.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_windows.ps1" %*
set EXIT_CODE=%ERRORLEVEL%

echo.
if %EXIT_CODE% neq 0 (
    echo Uzstadisana neizdevas. Exit code: %EXIT_CODE%
) else (
    echo Viss gatavs!
)
echo.
pause
exit /b %EXIT_CODE%
