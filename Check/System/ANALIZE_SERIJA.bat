@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "ROOT=%CD%"
set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
echo.
echo === TRADE SERIES ANALIZE ===
echo Root: %ROOT%
echo.

set "ACCOUNT=%~1"
if "%ACCOUNT%"=="" (
  for /d %%D in ("%ROOT%\data\clients\*") do (
    dir /b "%%D\market_*.csv" >nul 2>&1
    if not errorlevel 1 if "!ACCOUNT!"=="" set "ACCOUNT=%%~nxD"
  )
)

if "%ACCOUNT%"=="" (
  echo [KLUDA] Nav atrasts neviens data\clients\*\market_*.csv
  echo Lieto: ANALIZE_SERIJA.bat 231054
  pause
  exit /b 1
)

echo Account: %ACCOUNT%
"%PY%" "%ROOT%\tools\analyze_trade_series.py" --root "%ROOT%" --account %ACCOUNT%
echo.
pause
