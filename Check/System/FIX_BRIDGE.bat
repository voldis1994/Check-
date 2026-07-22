@echo off
setlocal EnableExtensions
title CHECK SYSTEM v2 - FIX BRIDGE
cd /d "%~dp0"

echo ============================================
echo  FIX: EA must write market/status files
echo ============================================
echo.
echo 1^) Deploying MQ4 again...
call "%~dp0scripts\deploy_mt4.bat"
echo.
echo 2^) MetaEditor:
echo    - Open CHECK_SYSTEM_V2.mq4
echo    - Press F7 ^(must be 0 errors^)
echo.
echo 3^) On NATURALGAS M1 chart, remove old EA, attach CHECK_SYSTEM_V2 again:
echo    Common tab:
echo      [x] Allow live trading
echo      [x] Allow DLL imports   ^<-- CRITICAL
echo    Inputs:
echo      MagicNumber    = 19942026
echo      BridgeRootPath = ^(LEAVE EMPTY for AUTO^)
echo.
echo 4^) Toolbar: AutoTrading button must be GREEN / ON
echo.
echo 5^) Experts tab must show:
echo    CHECK_SYSTEM_V2 initialized ... bridge=...\MQL4\Files\CHECK_SYSTEM
echo.
echo 6^) Then run START_LIVE.bat again
echo ============================================
pause
