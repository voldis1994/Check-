@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%CD%"

echo.
echo ============================================================
echo   SYSTEM - LIVE
echo ============================================================
echo.

if not exist "%ROOT%\config\system.json" (
  echo [KLUDA] Šeit nav SYSTEM projekts. Atver:
  echo   C:\Check\System
  pause
  exit /b 1
)

if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo Vispirms uzstāda... ^(UZSTADIT.bat^)
  call "%ROOT%\UZSTADIT.bat" --quiet
  if errorlevel 1 (
    echo.
    echo Uzstādīšana neizdevās. Palaid: UZSTADIT.bat
    pause
    exit /b 1
  )
)

set "PY=%ROOT%\.venv\Scripts\python.exe"
"%PY%" -m pip install -r "%ROOT%\requirements.txt" -q
if errorlevel 1 goto :fail

echo Sinhronizē ceļus...
"%PY%" "%ROOT%\scripts\sync_paths.py" --root "%ROOT%"
if errorlevel 1 goto :fail

echo SYSTEM root: %ROOT%
echo.
echo Palaižu engine... ^(Ctrl+C lai apturētu^)
echo.

"%PY%" "%ROOT%\run_live.py"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo Exit code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%

:fail
echo.
echo Palaišana neizdevās.
pause
exit /b 1
