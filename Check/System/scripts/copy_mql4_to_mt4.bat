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
if "%MISSING%"=="1" (
  echo [KLUDA] Trūkst failu. Pārbaudi, ka MT4 ceļš ir pareizā Terminal MQL4 mape.
  exit /b 1
)

echo Gatavs. MetaEditor: atver Experts\SYSTEM_EA.mq4 un spied F7 (Compile).
echo Jābūt 0 errors. Ja vēl "can't open Include" — nepareizs Terminal HASH ceļš.
echo.
echo EA chartā: SystemRootPath = %SYSTEM_ROOT%
echo            MagicNumber = kā config\system.json instances[].magic
echo            Allow DLL imports = YES
endlocal
exit /b 0
