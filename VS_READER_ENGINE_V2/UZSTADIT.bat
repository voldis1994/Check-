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

echo [1/5] Python vide...
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

echo [2/5] Bibliotēkas...
"%PYTHON_CMD%" -m pip install --upgrade pip -q
"%PYTHON_CMD%" -m pip install -r "%ROOT%\requirements-runtime.txt" -q
if errorlevel 1 goto :fail

echo [3/5] Datu mapes...
for %%D in (data\clients data\logs data\cache data\history data\universe) do (
  if not exist "%ROOT%\%%D" mkdir "%ROOT%\%%D"
)

echo [4/5] Config root_path...
"%PYTHON_CMD%" "%ROOT%\run_live.py" --setup-only 2>nul
if errorlevel 1 (
  "%PYTHON_CMD%" -c "import json;from pathlib import Path;r=Path(r'%ROOT%');c=r/'config'/'system.json';p=json.loads(c.read_text(encoding='utf-8'));p.setdefault('system',{})['root_path']=str(r).replace('\\','\\\\');c.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')"
)

echo [5/5] MT4 ceļš...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\generate_mql4_root.ps1" -RootPath "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo   GATAVS!
echo ============================================================
echo.
echo  Nākamais solis — palaid live:
echo    PALAID.bat
echo.
echo  MT4 (vienreiz):
echo    scripts\copy_mql4_to_mt4.bat "C:\ceļš\uz\MT4\MQL4"
echo    MetaEditor: Compile SYSTEM_EA.mq4
echo    EA iestatījumos SystemRootPath = %ROOT%
echo      (vai atstāj tukšu, ja generate_mql4_root jau izdarīts)
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
