@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Deploy CHECK_SYSTEM_V2.mq4 + Include/*.mqh into every MetaQuotes Terminal MQL4 tree.
cd /d "%~dp0\.."
set "ROOT=%CD%"
set "SRC_EA=%ROOT%\mt4\Experts\CHECK_SYSTEM_V2.mq4"
set "SRC_INC=%ROOT%\mt4\Include"
set "COPIED=0"

if not exist "%SRC_EA%" (
  echo [ERROR] Nav atrasts %SRC_EA%
  exit /b 1
)
if not exist "%SRC_INC%\CHECK_Protocol.mqh" (
  echo [ERROR] Nav atrasts Include faili: %SRC_INC%
  exit /b 1
)

REM Also keep a local deploy mirror under runtime\mt4_deploy for manual copy
set "MIRROR=%ROOT%\runtime\mt4_deploy"
if not exist "%MIRROR%\Experts" mkdir "%MIRROR%\Experts"
if not exist "%MIRROR%\Include" mkdir "%MIRROR%\Include"
copy /Y "%SRC_EA%" "%MIRROR%\Experts\CHECK_SYSTEM_V2.mq4" >nul
copy /Y "%SRC_INC%\CHECK_*.mqh" "%MIRROR%\Include\" >nul
echo   Mirror: %MIRROR%\Experts + Include

set "TERM_ROOT=%APPDATA%\MetaQuotes\Terminal"
if not exist "%TERM_ROOT%" (
  echo   [WARN] Nav %TERM_ROOT%
  echo   Atver MetaTrader 4 -^> File -^> Open Data Folder
  echo   un kopē no: %MIRROR%
  echo     Experts\CHECK_SYSTEM_V2.mq4 -^> MQL4\Experts\
  echo     Include\CHECK_*.mqh         -^> MQL4\Include\
  exit /b 0
)

for /d %%T in ("%TERM_ROOT%\*") do (
  if exist "%%T\MQL4" (
    if not exist "%%T\MQL4\Experts" mkdir "%%T\MQL4\Experts"
    if not exist "%%T\MQL4\Include" mkdir "%%T\MQL4\Include"
    copy /Y "%SRC_EA%" "%%T\MQL4\Experts\CHECK_SYSTEM_V2.mq4" >nul
    copy /Y "%SRC_INC%\CHECK_*.mqh" "%%T\MQL4\Include\" >nul
    echo   OK: %%T\MQL4
    set /a COPIED+=1
  )
)

if %COPIED%==0 (
  echo   [WARN] Neviena Terminal\...\MQL4 mape netika atrasta.
  echo   Izmanto mirror: %MIRROR%
  exit /b 0
)

echo   EA ielikts %COPIED% MetaTrader Data Folder^(s^).
echo   Tagad MetaEditor -^> F7 compile CHECK_SYSTEM_V2.mq4
exit /b 0
