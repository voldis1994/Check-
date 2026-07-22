@echo off
setlocal EnableExtensions EnableDelayedExpansion
title CHECK SYSTEM v2.0.0 - Full Setup
cd /d "%~dp0"
set "ROOT=%CD%"

echo ============================================
echo   CHECK SYSTEM v2.0.0 - FULL SETUP
echo   Root: %ROOT%
echo ============================================
echo.

REM ---------- Python 3.12+ ----------
set "PY="
where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3.12 -c "import sys" >nul 2>&1
  if !ERRORLEVEL!==0 set "PY=py -3.12"
)
if not defined PY (
  where python >nul 2>&1
  if !ERRORLEVEL!==0 (
    for /f "tokens=2 delims= " %%V in ('python -c "import sys; print(sys.version)" 2^>nul') do set "VER=%%V"
    python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,12) else 1)" >nul 2>&1
    if !ERRORLEVEL!==0 set "PY=python"
  )
)
if not defined PY (
  echo [ERROR] Python 3.12+ nav PATH.
  echo Uzliec no https://www.python.org/downloads/ ar "Add to PATH".
  echo Peci palaid so SETUP_ALL.bat velreiz.
  pause
  exit /b 1
)
echo [1/5] Python OK: %PY%
%PY% -c "import sys; print('     ', sys.version)"

REM ---------- pip install ----------
echo.
echo [2/5] Instalē checktrader...
%PY% -m pip install --upgrade pip
if errorlevel 1 goto :fail
%PY% -m pip install -e ".[dev]"
if errorlevel 1 goto :fail
echo       checktrader install OK

REM ---------- runtime + config ----------
echo.
echo [3/5] Runtime mapes + config...
for %%D in (
  "runtime\bridge\market"
  "runtime\bridge\status"
  "runtime\bridge\commands"
  "runtime\bridge\acknowledgements"
  "runtime\bridge\archive"
  "runtime\bridge\archive\commands"
  "runtime\state"
  "runtime\logs"
  "config\local"
) do if not exist "%%~D" mkdir "%%~D"

if not exist "config\local\system.json" (
  copy /Y "config\system.example.json" "config\local\system.json" >nul
  echo       Izveidots config\local\system.json
) else (
  echo       Saglabats esošais config\local\system.json
)

REM Iestata paths.root + symbol=AUTO
%PY% tools\seed_local_config.py --root "%ROOT%"
if errorlevel 1 goto :fail

echo.
echo       Account + symbol = AUTO (nem no MT4).
echo       Vajadzibas gadijuma vari pinat kontus allowed_account_numbers.
echo.

REM ---------- MT4 deploy ----------
echo [4/5] Kopē MQ4 EA + Include uz MetaTrader mapēm...
call "%ROOT%\scripts\deploy_mt4.bat"
if errorlevel 1 (
  echo       [WARN] Automātiska MT4 deploy neizdevās - skaties rokasgrāmatu zemāk.
)

REM ---------- Done ----------
echo.
echo [5/5] GATAVS
echo ============================================
echo  NAKAMIE SOLI:
echo  1^) MetaEditor: atver CHECK_SYSTEM_V2.mq4 -^> F7 ^(0 errors^)
echo  2^) Uzliec EA uz M1 chart ^(piem. NATURALGAS^)
echo     BridgeRootPath = %ROOT%
echo     MagicNumber    = 19942026
echo     Allow live trading + Allow DLL imports
echo  3^) Palaid:  START_LIVE.bat
echo     ^(simbols + konts nāk automātiski no MT4^)
echo ============================================
echo.
pause
exit /b 0

:fail
echo.
echo [FAIL] Setup apstajas ar kludu.
pause
exit /b 1
