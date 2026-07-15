@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
set "ROOT=%CD%"
set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo.
echo === KOPET MQL4 UZ MT4 + PARBAUDE ===
echo Root: %ROOT%
echo.
echo 1^) Palaid: scripts\copy_mql4_to_mt4.bat "C:\CELSH\UZ\MT4\MQL4"
echo 2^) MetaEditor: Compile SYSTEM_EA.mq4
echo 3^) EA uz EURUSD M1
echo 4^) Common: Allow DLL imports = YES
echo 5^) Inputs: SystemRootPath = %ROOT%
echo 6^) Experts loga mekle: SYSTEM export OK
echo.
"%PY%" "%ROOT%\scripts\sync_paths.py" --root "%ROOT%"
"%PY%" "%ROOT%\tools\show_paths.py" --root "%ROOT%"
echo.
pause
