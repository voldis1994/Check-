@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "ROOT=%CD%"

REM --- maximize CMD surface for the command center ---
chcp 65001 >nul
title SYSTEM COMMAND CENTER
mode con cols=120 lines=48 >nul 2>&1

REM Windows 10+ ANSI / VT colors in this console
reg add "HKCU\Console" /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>&1

echo.
echo ============================================================
echo   SYSTEM - LIVE COMMAND CENTER
echo ============================================================
echo.
echo   Konsoles feed + HTML dashboard parāda REĀLAS robota
echo   darbības no decision/trade/error journal, control, ACK,
echo   status, sensor un market failiem.
echo.
echo   Palaid PARALĒLI:  PALAID.bat  (engine)
echo                     DASHBOARD.bat (šis logs)
echo ============================================================
echo.

if not exist "%ROOT%\config\system.json" (
  echo [KLUDA] Seit nav SYSTEM projekts. Atver:
  echo   C:\Check\System
  pause
  exit /b 1
)

if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo Vispirms uzstada... ^(UZSTADIT.bat^)
  call "%ROOT%\UZSTADIT.bat" --quiet
  if errorlevel 1 (
    echo.
    echo Uzstadisana neizdevas. Palaid: UZSTADIT.bat
    pause
    exit /b 1
  )
)

set "PY=%ROOT%\.venv\Scripts\python.exe"
"%PY%" -m pip install -r "%ROOT%\requirements.txt" -q
if errorlevel 1 goto :fail

echo Sinhronize celus...
"%PY%" "%ROOT%\scripts\sync_paths.py" --root "%ROOT%"
if errorlevel 1 goto :fail

set "PORT=8765"
set "URL=http://127.0.0.1:%PORT%/"

echo.
echo ------------------------------------------------------------
echo  Web dashboard: %URL%
echo  CMD logā: live action feed ^(Ctrl+C aptur^)
echo ------------------------------------------------------------
echo.

REM Open browser after server bind (Windows start is most reliable in CMD)
start "" cmd /c "timeout /t 2 /nobreak >nul & start \"\" \"%URL%\""

"%PY%" -u "%ROOT%\dashboard.py" --web --port %PORT%
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo Exit code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%

:fail
echo.
echo Dashboard palaisana neizdevas.
pause
exit /b 1
