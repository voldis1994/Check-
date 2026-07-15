@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%CD%"
set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
echo.
echo === PARBAUDE: kapec SKIP ===
echo Root: %ROOT%
echo.
"%PY%" "%ROOT%\scripts\sync_paths.py" --root "%ROOT%" >nul 2>&1
"%PY%" "%ROOT%\tools\diagnose_skip.py" --root "%ROOT%"
echo.
pause
