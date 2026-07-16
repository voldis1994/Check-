# SYSTEM

Python M1 trading platform. Python decides. MT4 exports data and executes orders.

Recommended deploy root: `C:\Check\System` (any folder works after `UZSTADIT.bat`).

Trailing: fixed pips via `trade_management.trailing_step_pips` + structure lookback.

## New PC (full path)

```bat
cd C:\Check\System
UZSTADIT.bat
FIX_MT4.bat
```

Then in MetaEditor:

1. Open `Experts\SYSTEM_EA.mq4`
2. Press **F7 Compile** → **0 errors**
3. Attach EA to **EURUSD M1**
4. Common: **Allow DLL imports = YES**
5. Inputs: `SystemRootPath` = this folder (e.g. `C:\Check\System`)

Start live:

```bat
PALAID.bat
DASHBOARD.bat
```

`FIX_MT4.bat` copies **both** `Experts` and `Include\SYSTEM_*.mqh`.  
If compile says `can't open ...\Include\SYSTEM_...`, run `FIX_MT4.bat` again on the active Terminal data folder (File → Open Data Folder).

## Install from GitHub

```bat
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
```

Or quick ZIP installer:

```bat
powershell -ExecutionPolicy Bypass -File scripts\lejupielade_uzreiz.ps1
```

## Run

```bat
UZSTADIT.bat
PALAID.bat
```

`UZSTADIT.bat` / `PALAID.bat` run `scripts\sync_paths.py` so Python config, MQL4 root, and runtime root stay aligned.  
Account id in config auto-updates from the first `data\clients\<account>\market_*.csv` export.

## Tests

```bat
pytest
pytest tests/deployment -m deployment
```
