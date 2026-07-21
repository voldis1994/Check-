@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "ROOT=%CD%"

echo.
echo === KOPET MQL4 UZ MT4 + PARBAUDE ===
echo Root: %ROOT%
echo.

set "MT4_TARGET=%~1"
if not "%MT4_TARGET%"=="" goto :copy_one

echo Mekleju MetaQuotes Terminal MQL4 mapes...
set "COUNT=0"
set "FAIL=0"
for /d %%D in ("%APPDATA%\MetaQuotes\Terminal\*") do (
  if exist "%%D\MQL4" (
    set /a COUNT+=1
    echo.
    echo --- [!COUNT!] %%D\MQL4 ---
    call "%ROOT%\scripts\copy_mql4_to_mt4.bat" "%%D\MQL4"
    if errorlevel 1 (
      echo [KLUDA] Kopēšana neizdevās: %%D\MQL4
      set "FAIL=1"
    )
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

echo.
if not "%FAIL%"=="0" (
  echo [KLUDA] Dažas Terminal mapes neizdevās. Skat. augstāk.
  pause
  exit /b 1
)

echo === GATAVS: nokopēts uz %COUNT% Terminal MQL4 mapēm ===
echo.
echo MetaEditor ^(OBLIGATI no tā paša Terminal Data Folder^):
echo   1^) Aizver MetaEditor
echo   2^) MT4: File -^> Open Data Folder -^> MQL4\Experts\SYSTEM_EA.mq4
echo   3^) F7 Compile — jābūt 0 errors
echo   4^) EA uz EURUSD M1
echo   5^) Common: Allow DLL imports = YES
echo   6^) Inputs: SystemRootPath = %ROOT%
echo.
echo Ja joprojām "can't open ...\Include\SYSTEM_..." —
echo   atver tieši to HASH mapi no MetaEditor kļūdas, piem.:
echo   FIX_MT4.bat "%%APPDATA%%\MetaQuotes\Terminal\C879C699A2AEBE2E45B5D3054ECC35E8\MQL4"
echo.
pause
exit /b 0

:copy_one
echo.
echo Kopē uz: %MT4_TARGET%
echo.
call "%ROOT%\scripts\copy_mql4_to_mt4.bat" "%MT4_TARGET%"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [KLUDA] Kopēšana neizdevās.
  pause
  exit /b %RC%
)

echo MetaEditor:
echo   1^) Atver Experts\SYSTEM_EA.mq4 no šī Terminal Data Folder
echo   2^) F7 Compile — jābūt 0 errors
echo   3^) EA uz EURUSD M1
echo   4^) Common: Allow DLL imports = YES
echo   5^) Inputs: SystemRootPath = %ROOT%
echo.
pause
exit /b 0
