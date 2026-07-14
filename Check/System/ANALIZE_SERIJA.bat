@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%CD%"
set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
echo.
echo === TRADE SERIES ANALIZE ===
echo Root: %ROOT%
echo.
"%PY%" "%ROOT%\tools\analyze_trade_series.py" --root "%ROOT%" --account 231054
echo.
pause
