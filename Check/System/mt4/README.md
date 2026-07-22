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

`SETUP_ALL.bat` / `DEPLOY_MT4.bat` copy files into every:

`%APPDATA%\MetaQuotes\Terminal\<id>\MQL4\Experts\` and `...\Include\`

Also mirrors to `runtime/mt4_deploy/` for manual copy.

Then:

1. Open MetaTrader 4 → **File → Open Data Folder**.
2. Confirm `MQL4/Experts/CHECK_SYSTEM_V2.mq4` and `MQL4/Include/CHECK_*.mqh` exist.
3. In MetaEditor, open `CHECK_SYSTEM_V2.mq4`.
4. Press **F7** (Compile). The Errors tab must show **0** errors.
5. In the Terminal Navigator, refresh Experts if needed.

### Attach and configure

1. Open your symbol on **M1** (e.g. NATURALGAS).
2. Drag `CHECK_SYSTEM_V2` onto the chart.
3. On the **Common** tab: enable **Allow live trading** and **Allow DLL imports** (required).
4. Inputs:
   - `BridgeRootPath` — **leave EMPTY** for AUTO (`Terminal\MQL4\Files\CHECK_SYSTEM`)
     or set absolute `Check\System` folder if you prefer repo bridge
   - `MagicNumber` — must match config (default `19942026`)
5. Confirm AutoTrading is ON. Chart comment should show `CHECK V2 bridge=...`.

Python auto-discovers the MT4 Files bridge under `%APPDATA%\MetaQuotes\Terminal\`.

If Python says `waiting for market/status bridge files`, run `FIX_BRIDGE.bat`.

## Linux / CI note

MetaEditor cannot compile MQL4 on Linux CI. Protocol shapes and MODIFY protection rules are covered by Python fixtures under `tests/protocol/`.
