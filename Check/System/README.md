# SYSTEM

Python M1 trading platform. Python decides. MT4 exports data and executes orders.

Recommended deploy root: `C:\Check\System` (any folder works after `UZSTADIT.bat`).

Trailing: fixed pips via `trade_management.trailing_step_pips` + structure lookback.
Lot size: `risk.fixed_lot_volume` (active). `max_risk_per_trade_percent` is unused while fixed lot > 0.
News filter: disabled until a real calendar is connected (`metadata.news_data_available=false`).

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

## Multiple accounts on one PC

One Python root (`C:\Check\System`) + one `PALAID.bat` can run many accounts.  
Each account needs its **own MT4 terminal** (one login per terminal).

### Config

`config\system.json`:

```json
"instances": [
  { "account_id": "231054", "symbol": "EURUSD", "magic": 100001, "enabled": true },
  { "account_id": "OTRAIS_KONTS", "symbol": "EURUSD", "magic": 100002, "enabled": true }
]
```

Or start with one account — when the second EA exports `market_*.csv`, sync/auto-discover adds it.

### MT4

1. Terminal A → account 1, Terminal B → account 2
2. `FIX_MT4.bat` for **each** Terminal data folder
3. Compile EA in each MetaEditor
4. Each chart EURUSD M1:
   - AutoTrading ON
   - Allow DLL imports = YES
   - `SystemRootPath = C:\Check\System` (same path)
   - Magic `100001` / `100002`

### Run

```bat
PALAID.bat
DASHBOARD.bat
```

Dashboard shows one card per account. Files:

- `data\clients\231054\`
- `data\clients\OTRAIS_KONTS\`

Helper checklist: `KONTI.bat`

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
`instances[]` syncs from all `data\clients\<account>\market_*.csv` exports (multi-account aware).

## Tests

```bat
pytest
pytest tests/deployment -m deployment
```
