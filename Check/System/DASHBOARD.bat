@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%CD%"

echo.
echo ============================================================
echo   SYSTEM - LIVE COMMAND CENTER
echo ============================================================
echo.

if not exist "%ROOT%\config\system.json" (
  echo [KLUDA] Seit nav SYSTEM projekts. Atver:
  echo   C:\Check\System
  pause
  exit /b 1
)

if not exist "%ROOT%\dashboard.py" (
  echo [KLUDA] Nav dashboard.py
  echo Atjaunini mapi no GitHub main vai lejupielade jauno ZIP.
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

echo.
echo ------------------------------------------------------------
echo  PC:       http://127.0.0.1:8765/
echo  Telefons: http://TAVS_LAN_IP:8765/  ^(skaties zemak CMD^)
echo            127.0.0.1 telefonaa NESTRADA - tas ir pats telefons!
echo  Palaid PARALELI ari: PALAID.bat
echo ------------------------------------------------------------
echo.
echo Palauzu dashboard... ^(Ctrl+C lai apturetu^)
echo.

"%PY%" -u "%ROOT%\dashboard.py" --web --open-browser --bind-lan --port 8765
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
