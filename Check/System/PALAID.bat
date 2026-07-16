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
  echo [KLUDA] Seit nav SYSTEM projekts. Atver mapi ar run_live.py, piem.:
  echo   %ROOT%
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
echo  PIRMS STARTA PARBAUDI MT4:
echo    1. SYSTEM_EA uz EURUSD M1
echo    2. AutoTrading IESLEGTS
echo    3. SystemRootPath = %ROOT%
echo  Ja nav failu data\clients\<konts>\market_*.csv,
echo  Python gaidis ~90s, tad startes ar SKIP lidz EA raksta.
echo  Konta ID sinhronizes no pirmas market_*.csv mapes.
echo ------------------------------------------------------------
echo.
echo SYSTEM root: %ROOT%
echo.
echo Palauzu engine... ^(Ctrl+C lai apturetu^)
echo.

"%PY%" -u "%ROOT%\run_live.py"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo Exit code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%

:fail
echo.
echo Palaisana neizdevas.
pause
exit /b 1
