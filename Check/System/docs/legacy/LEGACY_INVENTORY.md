# Legacy V1 Inventory

Tag: `legacy-v1-final`  
Archive branch: `archive/legacy-v1`  
Snapshot commit: tip of PR #35 trailing work (v1.1.9)  
Purpose: document what existed before SYSTEM v2.0.0 rewrite.

## Release identity

| Item | Value |
|------|-------|
| VERSION | 1.1.9 |
| Protocol / config / state schema | 1.0.0 |
| Default root | `C:\Check\System` |
| Instance key | `(account_id, symbol, magic)` |
| Timeframe | M1 only |
| Configured instance | account `231054`, symbol `EURUSD`, magic `100001` |

## Python start points

| Entrypoint | Role |
|------------|------|
| `run_live.py` | Live loop: load config → `startup` → `run_runtime_cycles` |
| `dashboard.py` | Console / optional web dashboard on port 8765 |
| `tools/*.py` | validate_live, show_paths, diagnose_skip, replay_signals, analyze_trade_series |
| `scripts/sync_paths.py` | Path sync helper |

Package layout was flat under `engine/` (not `src/`).

## MT4 EA

- Expert: `mql4/Experts/SYSTEM_EA.mq4`
- Inputs: `MagicNumber=100001`, `SystemRootPath=""`
- Requires `PERIOD_M1`
- OnTick: export sensor/status ~500ms; on new M1 bar export market+universe; execute pending control

### Include files

`SYSTEM_Execution.mqh`, `SYSTEM_Control.mqh`, `SYSTEM_Status.mqh`, `SYSTEM_Universe.mqh`, `SYSTEM_Export.mqh`, `SYSTEM_IO.mqh`, `SYSTEM_Paths.mqh`, `SYSTEM_RootConfig.mqh`

## MT4 ↔ Python data files

Base: `data/clients/{account_id}/`

| File | Direction |
|------|-----------|
| `market_{symbol}_{magic}.csv` | MT4 → Python |
| `sensor_{symbol}_{magic}.csv` | MT4 → Python |
| `status_{account_id}.json` | MT4 → Python |
| `universe.json` | MT4 → Python |
| `control_{symbol}_{magic}.json` | Python → MT4 |
| `ack_{symbol}_{magic}.json` | MT4 → Python |
| `closed_{symbol}_{magic}.json` | MT4 → Python |
| `processed_cmd_{symbol}_{magic}.txt` | EA idempotence |
| `ticket_map_{symbol}_{magic}.txt` | EA ticket map |
| `state/instance_*.json`, `spread_*.json`, `monitoring_*.json` | Python state |
| `journal/decision_*.jsonl`, `trade_*.jsonl`, `error_*.jsonl` | Python journals |

## OPEN protocol (control)

Required envelope: `schema_version`, `timestamp_utc`, `command_id`, `account_id`, `symbol`, `magic`, `action`, `reason`, `decision_id`  
OPEN payload: `side`, `volume`, `stop_loss`, `take_profit` (+ `order_comment`)

## MODIFY protocol

Payload: `ticket`, `side`, `stop_loss`, `take_profit`  
Post-OrderModify ACK must include MT4 re-read `applied_stop_loss` / `applied_take_profit`.

## CLOSE protocol

Payload: `ticket`, `side`, `volume`

## ACK format

Required: `schema_version`, `timestamp_utc`, `command_id`, `account_id`, `symbol`, `magic`, `status`  
Optional: `ticket`, `error_code`, `error_message`, `fill_price`, `open_time_utc`, `volume`, `side`, `action`, `requested_stop_loss`, `applied_stop_loss`, `requested_take_profit`, `applied_take_profit`, `broker_error_code`  
Statuses in file: `SUCCESS`, `FAILED`, `REJECTED`, `ALREADY_PROCESSED` (`TIMEOUT` internal only)

## Status format

Required: `schema_version`, `timestamp_utc`, `account_id`, `connected`, `trade_allowed`, `balance`, `equity`, `margin_free`, `ea_version`  
Optional: `open_positions[]`, `tick_value`, `tick_size`, `stop_level`, `freeze_level`  
Position: `symbol`, `magic`, `ticket`, `side`, `volume`, optional entry/SL/TP/profit/swap/commission/comment

## Market data format

CSV columns: `time_utc, open, high, low, close, volume, symbol, timeframe, digits, point` (timeframe=M1)  
Sensor CSV: `time_utc, bid, ask, spread, spread_points, symbol, digits, point`

## Account / config structure

`system.json` sections: `system`, `paths`, `runtime`, `instances`, `risk`, `analysis`, `journal`, `trade_management`, `dashboard`, `logging`, `ai`, `signal_quality`

## Magic / symbol / timeframe (actual use)

- Magic: `100001` (config + EA default)
- Symbol: `EURUSD`
- Timeframe: `M1` only (no native M5/M15 export; analysis on M1 window)

## Trailing behavior (v1.1.9)

1. Activate when peak net profit ≥ `activation_profit_money` (0.50)
2. First lock: BE with net +0.20 account currency via tick_value/tick_size
3. Confirm only from ACK `applied_stop_loss` or status reconciliation
4. After BE: discrete `trailing_step_pips=3.0` grid only (no money-step fallback)
5. Never worsen SL; jumped steps counted; technical snapped to reached grid

## Legacy / duplicate surface (delete candidates)

- Root `.bat` wrappers: `START`, `PALAID`, `DASHBOARD`, `UZSTADIT`, `FIX_MT4`, `PARBAUDI`, `KONTI`, `ANALIZE_SERIJA`
- Overlapping docs: `IMPLEMENTATION_PLAN`, stale README version, PATH_CONTRACT references missing
- Flat `engine/` package (replaced by `src/checktrader/`)
- Score-based BUY vs SELL decision (`decision/scorer.py`) — not carried forward as entry rule
- Signal quality cooldowns / fingerprints as entry gates — replaced by setup identity without post-trade cooldown
- AI advisory layer — not required for v2 core
- Dual dashboard console+web intertwined with cycle — rebuilt simply

## Risks / ambiguities found

1. **Real account number in committed `system.json`** (`231054`) — must not appear in v2 public examples.
2. **M1-only data** while v2 strategy needs M15/M5/M1 — aggregation or multi-TF export required.
3. **Score-based entries** contradict v2 “concrete setup” rule — intentionally dropped.
4. **Cooldown after loss / fingerprint gates** block new unique setups — intentionally removed; only duplicate setup identity blocks.
5. **`allow_close: false`** in production config while trailing/exit pressure need CLOSE — v2 enables CLOSE with explicit reasons.
6. **Single control/ack filename overwrite** — v2 uses sequenced unique command/ack files.
7. **Python `hash()` risk** — v2 uses SHA-256 / UUID only for persistent IDs.
8. **Stale README / version drift** between VERSION, README, EA property.

## Preservation rules

- Do not delete `.git` or tag history.
- New `src/checktrader` must not import `engine.*`.
- Old algorithms rewritten cleanly with new tests when reused (BE+0.20, pip grid, applied SL ACK).
- Old MQL4 kept until `mt4/Experts/CHECK_SYSTEM_V2.mq4` protocol tests pass, then removed with delete report.
