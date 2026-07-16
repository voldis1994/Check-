@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%CD%"
set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo.
echo === VAIRAKI KONTI VIENA DATORA ===
echo Root: %ROOT%
echo.
echo 1^) Katrajam kontam savs MT4 terminalis ^(viens login = viens MT4^)
echo 2^) FIX_MT4.bat  — palaid katrai Terminal MQL4 mapei
echo 3^) MetaEditor F7 Compile SYSTEM_EA.mq4
echo 4^) EA uz EURUSD M1
echo      Allow DLL imports = YES
echo      SystemRootPath = %ROOT%
echo      MagicNumber unikals: 100001, 100002, ...
echo 5^) config\system.json instances[] — viens ieraksts uz kontu
echo 6^) PALAID.bat + DASHBOARD.bat  ^(viens Python procesam visiem kontiem^)
echo.
echo Config piemers:
echo   "instances": [
echo     { "account_id": "231054", "symbol": "EURUSD", "magic": 100001, "enabled": true },
echo     { "account_id": "OTRAIS",  "symbol": "EURUSD", "magic": 100002, "enabled": true }
echo   ]
echo.

if exist "%PY%" (
  echo Sinhronize un radu celus...
  "%PY%" "%ROOT%\scripts\sync_paths.py" --root "%ROOT%"
  "%PY%" "%ROOT%\tools\show_paths.py" --root "%ROOT%"
  echo.
  echo Aktivas instances no config + market_*.csv:
  "%PY%" -c "from pathlib import Path; from engine.core.config import load_system_config; from engine.core.lifecycle import build_system_paths, discover_instances; from engine.core.paths import SystemPaths; root=Path(r'%ROOT%'); cfg=load_system_config(root/'config'/'system.json', system_paths=SystemPaths(root)); paths=build_system_paths(cfg, runtime_root=root); [print(f'  {i.account_id} {i.symbol} magic={i.magic}') for i in discover_instances(cfg, paths)]"
)

echo.
pause
exit /b 0
