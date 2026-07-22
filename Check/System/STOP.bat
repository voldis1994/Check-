@echo off
setlocal
cd /d "%~dp0"
echo Creating kill switch runtime\STOP_TRADING
if not exist "runtime" mkdir "runtime"
echo. > "runtime\STOP_TRADING"
echo Stop signal set. Engine cycle will halt new risk.
pause
