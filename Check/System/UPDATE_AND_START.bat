@echo off
setlocal EnableExtensions
title CHECK SYSTEM v2 - UPDATE + START
cd /d "%~dp0"

echo Updating from GitHub main...
where git >nul 2>&1
if %ERRORLEVEL%==0 (
  git -C "%~dp0..\.." fetch origin main 2>nul
  git -C "%~dp0..\.." checkout main 2>nul
  git -C "%~dp0..\.." pull origin main
) else (
  echo [WARN] git nav PATH — lejupielade ZIP no:
  echo   https://github.com/voldis1994/Check-/archive/refs/heads/main.zip
  echo un aizvieto Check\System mapi, tad palaid START_LIVE.bat
  pause
  exit /b 1
)

echo.
call "%~dp0START_LIVE.bat"
