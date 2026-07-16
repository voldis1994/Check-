@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%CD%"

echo.
echo === KOPET MQL4 UZ MT4 + PARBAUDE ===
echo Root: %ROOT%
echo.

if "%~1"=="" (
  echo MetaTrader: File -^> Open Data Folder
  echo Tad šajā CMD ielīmē pilnu ceļu līdz MQL4 mapei, piem.:
  echo.
  echo   FIX_MT4.bat "C:\Users\voldi\AppData\Roaming\MetaQuotes\Terminal\XXXX\MQL4"
  echo.
  echo Vai:
  echo   scripts\copy_mql4_to_mt4.bat "C:\...\MQL4"
  echo.
  echo Pēc kopēšanas MetaEditor:
  echo   1^) Atver Experts\SYSTEM_EA.mq4
  echo   2^) F7 Compile — jābūt 0 errors
  echo   3^) EA uz EURUSD M1
  echo   4^) Common: Allow DLL imports = YES
  echo   5^) Inputs: SystemRootPath = %ROOT%
  echo   6^) Experts logā: SYSTEM export OK
  echo.
  echo JA KOMPILE RĀDA "can't open ...\Include\SYSTEM_..." —
  echo   Experts ir nokopēts, bet Include\SYSTEM_*.mqh NAV.
  echo   Palaid šo bat ar MQL4 ceļu ^(skat. augstāk^).
  echo.
  pause
  exit /b 1
)

call "%ROOT%\scripts\copy_mql4_to_mt4.bat" "%~1"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [KLUDA] Kopēšana neizdevās.
  pause
  exit /b %RC%
)
pause
exit /b 0
