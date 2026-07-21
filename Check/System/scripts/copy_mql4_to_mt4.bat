@echo off
setlocal EnableExtensions

if "%~1"=="" (
  echo.
  echo Lietošana:
  echo   %~nx0 "C:\ceļš\uz\MT4\MQL4"
  echo.
  echo Piemērs ^(Data Folder no MT4: File -^> Open Data Folder^):
  echo   %~nx0 "C:\Users\voldi\AppData\Roaming\MetaQuotes\Terminal\HASH\MQL4"
  echo.
  exit /b 1
)

set "MT4_ROOT=%~1"
set "SCRIPT_DIR=%~dp0"
set "SYSTEM_ROOT=%SCRIPT_DIR%.."
pushd "%SYSTEM_ROOT%"
set "SYSTEM_ROOT=%CD%"
popd

if not exist "%SYSTEM_ROOT%\mql4\Include\SYSTEM_Execution.mqh" (
  echo [KLUDA] SYSTEM mql4 nav atrasts: %SYSTEM_ROOT%\mql4
  exit /b 1
)

if /I not "%MT4_ROOT:~-4%"=="MQL4" (
  if exist "%MT4_ROOT%\MQL4" set "MT4_ROOT=%MT4_ROOT%\MQL4"
)

echo SYSTEM root: %SYSTEM_ROOT%
echo MT4 MQL4:    %MT4_ROOT%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%SYSTEM_ROOT%\scripts\generate_mql4_root.ps1" -RootPath "%SYSTEM_ROOT%"
if errorlevel 1 exit /b 1

if not exist "%MT4_ROOT%\Include" mkdir "%MT4_ROOT%\Include"
if not exist "%MT4_ROOT%\Experts" mkdir "%MT4_ROOT%\Experts"

echo Kopē Include (SYSTEM_*.mqh)...
xcopy /Y /I "%SYSTEM_ROOT%\mql4\Include\SYSTEM_*.mqh" "%MT4_ROOT%\Include\"
if errorlevel 1 (
  echo [KLUDA] Include kopēšana neizdevās.
  exit /b 1
)

echo.
echo Kopē Experts (SYSTEM_EA.mq4)...
xcopy /Y /I "%SYSTEM_ROOT%\mql4\Experts\SYSTEM_EA.mq4" "%MT4_ROOT%\Experts\"
if errorlevel 1 (
  echo [KLUDA] Experts kopēšana neizdevās.
  exit /b 1
)

echo.
echo === PARBAUDE ===
set "MISSING=0"
for %%F in (
  SYSTEM_RootConfig.mqh
  SYSTEM_Paths.mqh
  SYSTEM_IO.mqh
  SYSTEM_Export.mqh
  SYSTEM_Status.mqh
  SYSTEM_Control.mqh
  SYSTEM_Execution.mqh
  SYSTEM_Universe.mqh
) do (
  if exist "%MT4_ROOT%\Include\%%F" (
    echo   OK  Include\%%F
  ) else (
    echo   NAV Include\%%F
    set "MISSING=1"
  )
)
if exist "%MT4_ROOT%\Experts\SYSTEM_EA.mq4" (
  echo   OK  Experts\SYSTEM_EA.mq4
) else (
  echo   NAV Experts\SYSTEM_EA.mq4
  set "MISSING=1"
)

echo.
echo === FUNKCIJU PARBAUDE ^(veci Include = MetaEditor errors^) ===
findstr /C:"SYSTEM_LoadProcessedCommandId" "%MT4_ROOT%\Include\SYSTEM_Execution.mqh" >nul
if errorlevel 1 (
  echo   NAV SYSTEM_LoadProcessedCommandId iekša Include\SYSTEM_Execution.mqh
  set "MISSING=1"
) else (
  echo   OK  SYSTEM_LoadProcessedCommandId
)
findstr /C:"SYSTEM_ExportClosedTrade" "%MT4_ROOT%\Include\SYSTEM_Status.mqh" >nul
if errorlevel 1 (
  echo   NAV SYSTEM_ExportClosedTrade iekša Include\SYSTEM_Status.mqh
  set "MISSING=1"
) else (
  echo   OK  SYSTEM_ExportClosedTrade
)

echo.
if "%MISSING%"=="1" (
  echo [KLUDA] Trūkst failu/funkciju. Pārbaudi, ka MT4 ceļš ir pareizā Terminal MQL4 mape.
  echo Tad aizver MetaEditor, palaid FIX_MT4.bat vēlreiz, atver Experts\SYSTEM_EA.mq4 un F7.
  exit /b 1
)

echo Gatavs. MetaEditor: aizver visus SYSTEM_*.mqh tabus, atver Experts\SYSTEM_EA.mq4 un F7.
echo Jābūt 0 errors. Ja "can't open Include" — palaid FIX_MT4.bat (kopē uz VISĀM Terminal mapēm).
echo Nested includes lieto #include ^<SYSTEM_*.mqh^> (nevis quotes — quotes meklē Experts\).
echo.
echo EA chartā: SystemRootPath = %SYSTEM_ROOT%
echo            MagicNumber = kā config\system.json instances[].magic
echo            Allow DLL imports = YES
endlocal
exit /b 0
