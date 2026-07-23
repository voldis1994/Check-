@echo off
setlocal EnableExtensions EnableDelayedExpansion
title CHECK SETUP
cd /d "%~dp0"

echo.
echo  ========================================
echo   CHECK  -  one-shot setup
echo  ========================================
echo.

REM --- folders ---
if not exist "template" mkdir "template"
if not exist "clients" mkdir "clients"
if not exist "instances" mkdir "instances"
if not exist "runtime" mkdir "runtime"
if not exist "config" mkdir "config"
if not exist "mt4" mkdir "mt4"

if not exist "config\defaults.json" (
  if exist "config\defaults.json.example" copy /Y "config\defaults.json.example" "config\defaults.json" >nul
)

REM --- find original MT4 in template ---
set "MT4_TEMPLATE="
for /r "template" %%F in (terminal.exe) do (
  if exist "%%F" (
    set "MT4_TEMPLATE=%%~dpF"
    goto :found_mt4
  )
)

echo  [FAIL] No terminal.exe under Check\template\
echo.
echo  Put your ORIGINAL MetaTrader 4 folder here:
echo    Check\template\MetaTrader 4\
echo    (must contain terminal.exe)
echo.
echo  Then run SETUP.bat again.
echo.
pause
exit /b 1

:found_mt4
echo  [OK] Template MT4: %MT4_TEMPLATE%

REM strip trailing backslash for robocopy
set "MT4_SRC=%MT4_TEMPLATE%"
if "%MT4_SRC:~-1%"=="\" set "MT4_SRC=%MT4_SRC:~0,-1%"

REM --- master working copy (shared base; accounts clone from this) ---
set "MT4_MASTER=%CD%\instances\_master"
echo  [..] Sync master instance from template ...
if not exist "%MT4_MASTER%" mkdir "%MT4_MASTER%"
robocopy "%MT4_SRC%" "%MT4_MASTER%" /E /XO /NFL /NDL /NJH /NJS /nc /ns /np >nul
set "RC=%ERRORLEVEL%"
if %RC% GEQ 8 (
  echo  [FAIL] robocopy failed code %RC%
  pause
  exit /b 1
)
echo  [OK] Master: %MT4_MASTER%

REM --- install EA into master ---
if not exist "mt4\CHECK.mq4" (
  echo  [FAIL] missing mt4\CHECK.mq4
  pause
  exit /b 1
)
if not exist "%MT4_MASTER%\MQL4\Experts" mkdir "%MT4_MASTER%\MQL4\Experts"
copy /Y "mt4\CHECK.mq4" "%MT4_MASTER%\MQL4\Experts\CHECK.mq4" >nul
if exist "mt4\CHECK.ex4" copy /Y "mt4\CHECK.ex4" "%MT4_MASTER%\MQL4\Experts\CHECK.ex4" >nul
if not exist "%MT4_MASTER%\MQL4\Files\CHECK\market" mkdir "%MT4_MASTER%\MQL4\Files\CHECK\market"
if not exist "%MT4_MASTER%\MQL4\Files\CHECK\status" mkdir "%MT4_MASTER%\MQL4\Files\CHECK\status"
if not exist "%MT4_MASTER%\MQL4\Files\CHECK\commands" mkdir "%MT4_MASTER%\MQL4\Files\CHECK\commands"
if not exist "%MT4_MASTER%\MQL4\Files\CHECK\acks" mkdir "%MT4_MASTER%\MQL4\Files\CHECK\acks"
echo  [OK] EA installed into master Experts

REM --- best-effort compile ---
set "EDITOR="
if exist "%MT4_MASTER%\metaeditor.exe" set "EDITOR=%MT4_MASTER%\metaeditor.exe"
if defined EDITOR (
  echo  [..] Compiling CHECK.mq4 ...
  "%EDITOR%" /compile:"%MT4_MASTER%\MQL4\Experts\CHECK.mq4" /log >nul 2>&1
  if exist "%MT4_MASTER%\MQL4\Experts\CHECK.ex4" (
    echo  [OK] CHECK.ex4 ready
  ) else (
    echo  [WARN] Compile skipped/failed - open CHECK.mq4 in MetaEditor and press F7
  )
) else (
  echo  [WARN] metaeditor.exe not in template - compile CHECK.mq4 with F7 once
)

REM --- seed defaults ---
if not exist "config\defaults.json" (
  echo {"magic":50001,"cycle_sec":3.0,"trend":true,"breakout":true,"symbol":"AUTO"}> "config\defaults.json"
)
if not exist "config\settings.json" copy /Y "config\defaults.json" "config\settings.json" >nul
echo  [OK] config ready

REM --- write template path marker ---
> "runtime\template_mt4.txt" echo %MT4_SRC%
> "runtime\master_mt4.txt" echo %MT4_MASTER%

REM --- sync EA into every existing account instance ---
for /d %%D in ("instances\*") do (
  if /I not "%%~nxD"=="_master" (
    if exist "%%D\MQL4\Experts" (
      copy /Y "mt4\CHECK.mq4" "%%D\MQL4\Experts\CHECK.mq4" >nul
      if exist "mt4\CHECK.ex4" copy /Y "mt4\CHECK.ex4" "%%D\MQL4\Experts\CHECK.ex4" >nul
      if exist "%MT4_MASTER%\MQL4\Experts\CHECK.ex4" copy /Y "%MT4_MASTER%\MQL4\Experts\CHECK.ex4" "%%D\MQL4\Experts\CHECK.ex4" >nul
    )
  )
)

REM --- python / exe ---
set "PYTHONPATH=%CD%;%PYTHONPATH%"

where python >nul 2>&1
if errorlevel 1 (
  echo  [WARN] Python not in PATH - if you already built CHECK.exe, continuing
) else (
  python -c "import tkinter" 1>nul 2>nul
  if errorlevel 1 (
    echo  [FAIL] Python needs Tcl/Tk. Install Python 3.12+ with tcl/tk.
    pause
    exit /b 1
  )
  echo  [OK] Python + Tk
)

REM optional: build EXE if PyInstaller available and no dist yet
if not exist "dist\CHECK\CHECK.exe" (
  where python >nul 2>&1
  if not errorlevel 1 (
    python -c "import PyInstaller" 1>nul 2>nul
    if not errorlevel 1 (
      echo  [..] Building CHECK.exe ...
      python -m PyInstaller --noconfirm --clean "CHECK.spec" >nul 2>&1
      if exist "dist\CHECK\CHECK.exe" (
        if not exist "dist\CHECK\config" mkdir "dist\CHECK\config"
        if not exist "dist\CHECK\mt4" mkdir "dist\CHECK\mt4"
        copy /Y "config\defaults.json" "dist\CHECK\config\" >nul
        copy /Y "mt4\CHECK.mq4" "dist\CHECK\mt4\" >nul
        echo  [OK] dist\CHECK\CHECK.exe
      ) else (
        echo  [WARN] EXE build skipped - will run with python
      )
    )
  )
)

echo.
echo  ========================================
echo   SETUP COMPLETE
echo  ========================================
echo   1. Open CHECK desk
echo   2. ACCOUNTS - add login/password/server
echo      + set SL / BE / TRAIL points PER ACCOUNT
echo   3. LAUNCH opens that account MT4 clone
echo   4. Attach CHECK on M1  ^(BridgePath empty^)
echo   5. START LIVE
echo  ========================================
echo.

if exist "dist\CHECK\CHECK.exe" (
  start "" "%CD%\dist\CHECK\CHECK.exe"
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo  [FAIL] No CHECK.exe and no Python.
    pause
    exit /b 1
  )
  start "" python -m app.main
)

exit /b 0
