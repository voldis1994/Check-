@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%CD%"
set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
echo.
echo === MT4 PEER SALIDZINAJUMS ===
echo Root: %ROOT%
echo.
"%PY%" "%ROOT%\tools\compare_mt4_peers.py" --root "%ROOT%"
echo.
pause
