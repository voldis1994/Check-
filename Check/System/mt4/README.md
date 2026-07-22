# CHECK MT4 V2 (file bridge)

Expert Advisor + includes that speak protocol **2.0.0** with the Python engine under `runtime/bridge/`.

## Layout

| Path | Role |
|------|------|
| `Experts/CHECK_SYSTEM_V2.mq4` | EA entrypoint (M1 only) |
| `Include/CHECK_Protocol.mqh` | Protocol constants, bridge paths, atomic IO |
| `Include/CHECK_Json.mqh` | JSON escape / format / field extract helpers |
| `Include/CHECK_Export.mqh` | Market + status snapshot writers |
| `Include/CHECK_Execution.mqh` | OPEN / MODIFY / CLOSE + ACK + idempotence |

## Bridge directories

Relative to `BridgeRootPath` (SYSTEM root):

```
runtime/bridge/market/
runtime/bridge/status/
runtime/bridge/commands/
runtime/bridge/acknowledgements/
runtime/bridge/archive/
runtime/bridge/archive/commands/
```

- Market file: `market/market_{SYMBOL}_{MAGIC}.json`
- Status file: `status/status_{ACCOUNT}.json`
- Command file: `commands/{sequence}_{command_id}.json`
- ACK file: `acknowledgements/{sequence}_{command_id}.ack.json`
- Processed IDs: `archive/processed_commands_{SYMBOL}_{MAGIC}.txt`

Writes are atomic: content goes to `*.tmp`, then `MoveFileExW` replace.

## MetaEditor compile steps

1. Open MetaTrader 4 → **File → Open Data Folder**.
2. Copy `mt4/Experts/CHECK_SYSTEM_V2.mq4` into `MQL4/Experts/`.
3. Copy all `mt4/Include/CHECK_*.mqh` into `MQL4/Include/`.
4. In MetaEditor, open `CHECK_SYSTEM_V2.mq4`.
5. Press **F7** (Compile). The Errors tab must show **0** errors.
6. In the Terminal Navigator, refresh Experts if needed.

### Attach and configure

1. Open an **EURUSD M1** chart (or your configured symbol on M1).
2. Drag `CHECK_SYSTEM_V2` onto the chart.
3. On the **Common** tab: enable **Allow live trading** and **Allow DLL imports** (required for absolute-path bridge IO via `kernel32.dll`).
4. Inputs:
   - `BridgeRootPath` — absolute SYSTEM root (folder that contains `runtime/`), e.g. `C:\Check\System`
   - `MagicNumber` — must match `config` / `position.magic_number` (example default `19942026`)
5. Confirm Experts is enabled (toolbar AutoTrading / Expert Advisors).

### Verify

Within about one second of ticks you should see:

- `runtime/bridge/market/market_*.json`
- `runtime/bridge/status/status_*.json`

Python (`python -m checktrader`) reads the latest JSON in those folders.

## Linux / CI note

MetaEditor cannot compile MQL4 on Linux CI. Protocol shapes and MODIFY protection rules are covered by Python fixtures under `tests/protocol/`.
