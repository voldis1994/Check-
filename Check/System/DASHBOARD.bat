@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%CD%"

echo.
echo ============================================================
echo   SYSTEM - LIVE COMMAND CENTER  (PC + TELEFONS)
echo ============================================================
echo.

if not exist "%ROOT%\config\system.json" (
  echo [KLUDA] Seit nav SYSTEM projekts. Atver mapi ar dashboard.py, piem.:
  echo   %ROOT%
  pause
  exit /b 1
)

if not exist "%ROOT%\dashboard.py" (
  echo [KLUDA] Nav dashboard.py
  echo Atjaunini mapi no GitHub main.
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
echo  DATORA PARLUKS:   http://127.0.0.1:8765/
echo  TELEFONS:         LAN URL, ko Python izdrukas zemak
echo                    (PARBAUDI PC un telefons ir TADAS PASAS WiFi)
echo  QR:               atver dashboard -^> cilne PHONE
echo  127.0.0.1 telefona NESTRADA!
echo  Paraleli palaid:  PALAID.bat
echo ------------------------------------------------------------
echo.
echo Palauzu mobile dashboard... ^(Ctrl+C aptur^)
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
