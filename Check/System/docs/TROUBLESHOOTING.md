# Troubleshooting

## Stale market / status data

**Symptoms:** cycles log `DATA_STALE`; health shows old `generated_at_utc`; no new entries.

**Checks:**

1. EA attached to correct symbol on **M1**, AutoTrading on
2. `BridgeRootPath` empty (AUTO → `MQL4\Files\CHECK_SYSTEM`) or absolute path to SYSTEM root (contains `runtime/`)
3. Files updating under `runtime/bridge/market/` and `runtime/bridge/status/`
4. Clock skew — timestamps must be UTC `...Z`
5. Config ages: `execution.maximum_market_age_ms` / `maximum_status_age_ms`

**Fix:** reattach EA, fix path, enable DLLs, wait for ticks; use `python tools/inspect_bridge.py`.

If logs flip between two `account=` / `bridge=mt4-files:...` values every second, you have **two MT4 terminals** both writing bridges. `START_LIVE` now locks to one for the session — still prefer **one** live terminal, or pin `account.allowed_account_numbers` to the account you want.

`NO_SIGNAL` with `action=NONE` means the stack is healthy and waiting for a TREND_PULLBACK_BREAK setup — not a bridge failure.

## Broker error 130 (invalid stops)

SL/TP too close to market or wrong side of price; stop/freeze levels violated.

- Widen invalidation / respect `stop_level_points`
- Confirm digits / pip_size in market snapshot
- Do not send MODIFY that does not improve protection

## Broker error 136 (off quotes / market closed)

No reliable quote for trade.

- Confirm `market_open` / session
- Retry after quotes resume; reduce aggression during rollover

## Broker error 138 (requote)

Price moved beyond slippage.

- Increase `slippage_points` carefully
- Prefer waiting for fresh bid/ask in market snapshot before OPEN/CLOSE

## Broker error 145 (modification denied / trade context busy)

OrderModify rejected (freeze level, trade context, or concurrent trade).

- Keep pending SL and retry with backoff (`maximum_retries` / `retry_delay_ms`)
- Confirm freeze level; avoid overlapping MODIFY commands

## DLL imports

Absolute-path bridge IO uses Windows `kernel32` APIs. Without **Allow DLL imports** on the EA, market/status may never write (or write only relative paths incorrectly).

Enable on the EA Common tab; recompile if includes changed.

## Kill switch

File: `runtime/STOP_TRADING`

- Present → live loop treats kill switch active (no new risk)
- Create via `scripts/stop.ps1`
- Remove the file to allow trading again after restart/health check

If the engine process is still running with the file present, it should idle; if you need a hard stop, stop the Python process after engaging the switch.

## Account / config rejects

- Empty `allowed_account_numbers` → live start fails validation
- Status account not in allow-list → cycle rejects
- `require_expert_enabled` / `require_trade_allowed` → verify status flags

## Trailing not advancing

Usually confirmation rules:

- ACK missing `applied_stop_loss` or mismatch → `TRAILING_ACK_SL_MISMATCH`
- Confirm with status SL reconcile
- See `docs/TRAILING.md`

## Tools

```powershell
python tools\validate_config.py --config config\local\system.json
python tools\inspect_bridge.py
python tools\reconcile_account.py --config config\local\system.json
.\scripts\health.ps1
```
