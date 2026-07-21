@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%CD%"

echo.
echo ============================================================
echo   SYSTEM - UZSTADISANA (viena reize šajā mapē)
echo ============================================================
echo.
echo  Mape: %ROOT%
echo.

set "PYTHON_CMD="
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON_CMD=%ROOT%\.venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%ROOT%\.venv\Scripts\py.exe" set "PYTHON_CMD=%ROOT%\.venv\Scripts\py.exe"
if not defined PYTHON_CMD (
  where py >nul 2>&1 && set "PYTHON_LAUNCHER=py"
  if not defined PYTHON_LAUNCHER where python >nul 2>&1 && set "PYTHON_LAUNCHER=python"
  if not defined PYTHON_LAUNCHER (
    echo [KLUDA] Nav atrasts Python. Instalē no https://www.python.org/downloads/
    echo         Atzīmē "Add Python to PATH" instalācijas laikā.
    goto :fail
  )
)

if not exist "%ROOT%\config\system.json" (
  echo [KLUDA] Nav config\system.json mapē %ROOT%
  goto :fail
)

if not exist "%ROOT%\run_live.py" (
  echo [KLUDA] Nav run_live.py mapē %ROOT%
  goto :fail
)

echo [1/4] Python vide...
if not exist "%ROOT%\.venv\Scripts\python.exe" (
  if defined PYTHON_LAUNCHER (
    %PYTHON_LAUNCHER% -m venv "%ROOT%\.venv"
  ) else (
    echo [KLUDA] Nevar izveidot .venv
    goto :fail
  )
  if errorlevel 1 goto :fail
)
set "PYTHON_CMD=%ROOT%\.venv\Scripts\python.exe"

echo [2/4] Bibliotēkas...
"%PYTHON_CMD%" -m pip install --upgrade pip -q
"%PYTHON_CMD%" -m pip install -r "%ROOT%\requirements.txt" -q
if errorlevel 1 goto :fail

echo [3/4] Datu mapes...
for %%D in (data\clients data\logs data\cache data\history data\universe) do (
  if not exist "%ROOT%\%%D" mkdir "%ROOT%\%%D"
)

echo [4/4] Sinhronizē ceļus...
"%PYTHON_CMD%" "%ROOT%\scripts\sync_paths.py" --root "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo   GATAVS!
echo ============================================================
echo.
echo  Nakamais solis — palaid live:
echo    PALAID.bat
echo  Un atveri live dashboard ^(otra CMD loga^):
echo    DASHBOARD.bat
echo.
echo  MT4 (vienreiz — Obligati gan Experts, gan Include):
echo    FIX_MT4.bat
echo      ^(kopē uz VISĀM %%APPDATA%%\MetaQuotes\Terminal\*\MQL4^)
echo    MetaEditor: F7 Compile SYSTEM_EA.mq4  ^(0 errors^)
echo    EA: Allow DLL imports=YES, SystemRootPath=%ROOT%
echo    Ja "can't open ...\Include\SYSTEM_..." — aizver MetaEditor, FIX_MT4.bat atkartoti.
echo.
echo  Vairaki konti viena PC: KONTI.bat
echo    ^(katram kontam savs MT4 terminalis + cits MagicNumber^)
echo.
if /I "%~1"=="--quiet" exit /b 0
pause
exit /b 0

:fail
echo.
echo Uzstādīšana neizdevās.
if /I "%~1"=="--quiet" exit /b 1
pause
exit /b 1
