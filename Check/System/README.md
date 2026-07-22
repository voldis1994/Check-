# CHECK SYSTEM v2.0.0

Deterministic Python + MetaTrader 4 live trading bridge.

**Technical operability is not a profit guarantee.** A green health check, successful OPEN/MODIFY/CLOSE cycle, or passing test suite only means the stack can run and follow its rules. It does not imply edge, expectancy, or that live trading will be profitable.

## What this is

- One strategy: `TREND_PULLBACK_BREAK` (M15 context → M5 pullback → M1 break)
- Protective management: BE net +0.20, then 3-pip grid, high-lock, exit pressure
- Atomic JSON file bridge under `runtime/bridge/`
- Broker state is truth; MODIFY confirmation requires applied SL from ACK or status

## Install

Requires Python 3.12+.

```powershell
cd Check\System
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Or run `scripts\install.ps1`.

## Config

1. Copy the example config into the local (gitignored) path:

```powershell
New-Item -ItemType Directory -Force -Path config\local | Out-Null
Copy-Item config\system.example.json config\local\system.json
```

2. Edit `config/local/system.json`:
   - Set `account.allowed_account_numbers` to your live MT4 account(s) (empty list fails live start)
   - Set `paths.root` to the SYSTEM root if needed
   - Align `position.magic_number` with the EA input

## MT4 EA

Source path: `mt4/Experts/CHECK_SYSTEM_V2.mq4` (includes under `mt4/Include/`).

1. Copy EA + includes into the MT4 data folder `MQL4/Experts` and `MQL4/Include`
2. Compile in MetaEditor (F7) — 0 errors
3. Attach to the configured symbol on **M1**
4. Enable **Allow live trading** and **Allow DLL imports**
5. Set `BridgeRootPath` to this SYSTEM root (folder that contains `runtime/`)

See `mt4/README.md` and `docs/MT4_PROTOCOL.md`.

## Run live

```powershell
# checklist + start
.\scripts\start_live.ps1

# or directly
python -m checktrader --config config\local\system.json
```

Kill switch: create `runtime/STOP_TRADING` (empty file is enough). The live loop skips new risk and respects the switch; `scripts\stop.ps1` creates it.

## Ops scripts (Windows)

| Script | Purpose |
|--------|---------|
| `scripts/install.ps1` | Editable install + runtime dirs + local config seed |
| `scripts/start_live.ps1` | Validate config/accounts/bridge, then start engine |
| `scripts/stop.ps1` | Engage kill switch / stop process |
| `scripts/health.ps1` | Config, bridge heartbeat, kill switch, state |
| `scripts/run_tests.ps1` | Pytest for v2 suites |

## Tools

```powershell
python tools\validate_config.py --config config\local\system.json
python tools\inspect_bridge.py
python tools\reconcile_account.py --config config\local\system.json
python tools\export_audit.py --out runtime\logs\audit_export.jsonl
python tools\replay.py --market path\to\market.json --status path\to\status.json
```

## Docs

- `docs/ARCHITECTURE.md` — package layout and cycle
- `docs/LIVE_OPERATION.md` — live start checklist
- `docs/MT4_PROTOCOL.md` — bridge message contract
- `docs/STRATEGY.md` — setup rules
- `docs/TRAILING.md` — BE + pip grid confirmation
- `docs/EXIT_PRESSURE.md` — pressure components
- `docs/RISK.md` — sizing modes
- `docs/TROUBLESHOOTING.md` — common failures

## Tests / CI

```powershell
pip install -e ".[dev]"
python -m pytest tests/unit tests/integration tests/protocol tests/strategy tests/risk tests/trailing tests/state tests/e2e -q
```

## Disclaimer

This software automates order placement against a live broker when configured to do so. You are solely responsible for account selection, capital at risk, and regulatory compliance. **Passing health checks and tests is not a guarantee of trading profit.**
