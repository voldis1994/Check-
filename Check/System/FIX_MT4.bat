@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "ROOT=%CD%"

echo.
echo === KOPET MQL4 UZ MT4 + PARBAUDE ===
echo Root: %ROOT%
echo.

set "MT4_TARGET=%~1"
if not "%MT4_TARGET%"=="" goto :copy

echo Mekleju MetaQuotes Terminal MQL4 mapes...
set "FOUND="
set "COUNT=0"
for /d %%D in ("%APPDATA%\MetaQuotes\Terminal\*") do (
  if exist "%%D\MQL4" (
    set /a COUNT+=1
    set "FOUND=%%D\MQL4"
    echo   [!COUNT!] %%D\MQL4
  )
)

if "%COUNT%"=="0" (
  echo [KLUDA] Nav atrasta neviena ...\MetaQuotes\Terminal\*\MQL4
  echo MT4: File -^> Open Data Folder, tad:
  echo   FIX_MT4.bat "C:\Users\...\MetaQuotes\Terminal\HASH\MQL4"
  echo.
  pause
  exit /b 1
)

if "%COUNT%"=="1" (
  set "MT4_TARGET=%FOUND%"
  echo.
  echo Atlasita vieniga Terminal mape:
  echo   %MT4_TARGET%
  echo.
  goto :copy
)

echo.
echo Atrastas %COUNT% Terminal mapes. Noradi numuru vai ielime pilnu MQL4 celu.
set /p "CHOICE=Izvele: "
if exist "%CHOICE%\Experts" set "MT4_TARGET=%CHOICE%"
if exist "%CHOICE%" if /I "%CHOICE:~-4%"=="MQL4" set "MT4_TARGET=%CHOICE%"
if "%MT4_TARGET%"=="" (
  set "IDX=0"
  for /d %%D in ("%APPDATA%\MetaQuotes\Terminal\*") do (
    if exist "%%D\MQL4" (
      set /a IDX+=1
      if "!IDX!"=="%CHOICE%" set "MT4_TARGET=%%D\MQL4"
    )
  )
)

if "%MT4_TARGET%"=="" (
  echo [KLUDA] Nederiga izvele.
  pause
  exit /b 1
)

:copy
echo.
echo Kopē uz: %MT4_TARGET%
echo.
call "%ROOT%\scripts\copy_mql4_to_mt4.bat" "%MT4_TARGET%"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [KLUDA] Kopesana neizdevas.
  pause
  exit /b %RC%
)

echo MetaEditor:
echo   1^) Atver Experts\SYSTEM_EA.mq4
echo   2^) F7 Compile — jabut 0 errors
echo   3^) EA uz EURUSD M1
echo   4^) Common: Allow DLL imports = YES
echo   5^) Inputs: SystemRootPath = %ROOT%
echo   6^) Experts loga: SYSTEM export OK
echo.
pause
exit /b 0
