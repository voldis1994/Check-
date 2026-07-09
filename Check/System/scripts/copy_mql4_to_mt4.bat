@echo off
setlocal EnableExtensions

if "%~1"=="" (
  echo.
  echo Lietošana:
  echo   %~nx0 "C:\ceļš\uz\MT4\MQL4"
  echo.
  echo Piemērs:
  echo   %~nx0 "C:\VS1\VS_STAGE_02_MT4_MANAGER\mt4_template\MQL4"
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

echo SYSTEM root: %SYSTEM_ROOT%
echo MT4 MQL4:    %MT4_ROOT%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%SYSTEM_ROOT%\scripts\generate_mql4_root.ps1" -RootPath "%SYSTEM_ROOT%"
if errorlevel 1 exit /b 1

if not exist "%MT4_ROOT%\Include" mkdir "%MT4_ROOT%\Include"
if not exist "%MT4_ROOT%\Experts" mkdir "%MT4_ROOT%\Experts"

echo Kopē Include...
xcopy /Y /I "%SYSTEM_ROOT%\mql4\Include\SYSTEM_*.mqh" "%MT4_ROOT%\Include\" >nul

echo Kopē Experts...
xcopy /Y /I "%SYSTEM_ROOT%\mql4\Experts\SYSTEM_EA.mq4" "%MT4_ROOT%\Experts\" >nul

echo.
echo Gatavs. MetaEditor: atver SYSTEM_EA.mq4 un spied F7 (Compile).
echo EA chartā: SystemRootPath = %SYSTEM_ROOT%
echo            MagicNumber = kā config\system.json instances[].magic
endlocal
exit /b 0
