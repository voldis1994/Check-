# Troubleshooting

## Compile errors: `cannot open include file CHECK_V3_*.mqh`

MetaEditor cannot find the headers in that terminal's data folder.

1. Double-click `DEPLOY_MT4.bat` (or run `.\scripts\deploy_mt4.ps1`).
2. Confirm these files exist under the **same** terminal hash you compile:
   - `...\MQL4\Experts\CHECK_SYSTEM_V3.mq4`
   - `...\MQL4\Experts\CHECK_V3_Protocol.mqh` (+ Bridge / Market / Execution)
   - `...\MQL4\Include\CHECK_V3_*.mqh`
3. Open the EA from **File → Open Data Folder → MQL4\Experts**, not only from the git clone.
4. Press **F7** again (must be 0 errors).

## EA does not initialize

Check:

- The chart timeframe is M1.
- **Allow DLL imports** is enabled for the EA.
- The MT4 Experts tab has no compile/runtime errors.
- The bridge path is writable.

## No MARKET or STATUS files

Check:

- EA chart comment shows the expected bridge path.
- `runtime\bridge\market` and `runtime\bridge\status` exist.
- MT4 is connected to the broker.
- The symbol chart has loaded M1 history.

Run:

```powershell
.\scripts\health.ps1
python .\tools\inspect_bridge.py --bridge runtime\bridge
```

## Python cannot find the bridge

Set `paths.bridge_dir` in the config to the exact bridge directory or configure discovery roots. The MT4 EA default root is:

```text
TerminalDataPath\MQL4\Files\CHECK_SYSTEM
```

The bridge directory below that root is:

```text
runtime\bridge
```

## Commands are not executed

Check:

- AutoTrading is enabled in MT4.
- The EA is still attached to the M1 chart.
- The command `symbol` matches the chart symbol.
- `protocol_version` is `3.0.0`.
- `command_id` is unique for new commands.
- The command has not already produced an `archive\processed_<command_id>.json` marker.

Inspect ACK files for `broker_error` and `broker_error_message`.

## Broker rejects an OPEN command

Common causes:

- Invalid volume or lot step.
- Stop loss or take profit violates broker stop/freeze levels.
- Market is closed.
- Off quotes or requote.
- Not enough free margin.
- Trading disabled by broker or terminal.

The EA records the broker error in ACK JSON.

## MODIFY or CLOSE rejects with ticket not found

Check that `position_id` or `ticket` matches an open MT4 order ticket on the same terminal/account. The bridge is account-local; tickets from another terminal cannot be selected.

## Stale market data

Check:

- MT4 connection status.
- Symbol market hours.
- Chart M1 history.
- Whether files in `market` and `status` are updating every timer/tick cycle.

## Stop sentinel exists

`runtime/STOP_TRADING` indicates an operator stop request. Remove it only after verifying the system is safe to resume.

## Audit questions

Use:

```powershell
python .\tools\explain_signal.py --audit runtime\audit.jsonl
python .\tools\export_audit.py --audit runtime\audit.jsonl --out runtime\audit_export.json
```

The audit file is JSONL: one JSON object per cycle.
