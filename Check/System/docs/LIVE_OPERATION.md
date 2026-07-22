# Live operation checklist

Windows live ops. Steps match `scripts/start_live.ps1`.

## Prerequisites

- Python 3.12+ on PATH
- Package installed: `pip install -e ".[dev]"` (or `scripts/install.ps1`)
- MT4 EA `CHECK_SYSTEM_V2` compiled and attached to the configured symbol on **M1**
- EA inputs: `BridgeRootPath` empty (AUTO) or SYSTEM root; `MagicNumber` matches config
- Experts + AutoTrading on; **Allow DLL imports** enabled

## Start checklist (`start_live.ps1`)

1. **Resolve SYSTEM root**  
   Script sets location to `Check/System` (parent of `scripts/`).

2. **Ensure local config**  
   If `config/local/system.json` is missing, copy from `config/system.example.json`.

3. **Validate config**  
   Run `python tools/validate_config.py --config config/local/system.json`.  
   Failures that block start:
   - missing / invalid JSON
   - empty `account.allowed_account_numbers` (live mode)
   - invalid risk / paths

4. **Confirm kill switch is clear**  
   `runtime/STOP_TRADING` must **not** exist (unless you intentionally start paused — then remove it when ready).

5. **Ensure runtime directories**  
   Create `runtime/bridge/{market,status,commands,acknowledgements,archive}`, `runtime/state`, `runtime/logs` if missing.

6. **Account allow-list**  
   Status snapshot `account_number` must be in `allowed_account_numbers`.  
   Script prints configured accounts; wrong account → cycle rejects with account mismatch.

7. **Bridge heartbeat**  
   Wait until fresh files exist under:
   - `runtime/bridge/market/*.json`
   - `runtime/bridge/status/*.json`  
   Default max age aligns with config `execution.maximum_market_age_ms` / `maximum_status_age_ms` (health script uses a few seconds).  
   If stale: fix EA chart, BridgeRootPath, DLL imports, or market session.

8. **Start engine**  
   `python -m checktrader --config config/local/system.json`

9. **Optional dashboard**  
   If `dashboard.enabled`, open `http://127.0.0.1:8765/` (default host/port from config).

## Stop

```powershell
.\scripts\stop.ps1
```

Creates `runtime/STOP_TRADING`. Remove the file to resume after a restart, or keep it to stay halted.

## Health

```powershell
.\scripts\health.ps1
```

Reports: config load, allowed accounts, kill switch, latest market/status age, instance state summary.

## Safety reminders

- Empty `allowed_account_numbers` is a **configuration error** for live start.
- Kill switch blocks new risk; open positions still need broker/EA for protective closes depending on cycle path — verify status before walking away.
- **Technical operability is not a profit guarantee.**
