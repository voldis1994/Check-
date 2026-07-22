# Architecture

CHECK SYSTEM v3 separates decision-making from broker execution.

## Components

1. **Python engine**
   - Loads and validates `SystemConfig`.
   - Maintains rolling market history and runtime state.
   - Detects market regime.
   - Routes strategies.
   - Applies risk validation and trade management.
   - Writes commands and audit records.

2. **MT4 bridge EA**
   - Runs on an M1 chart.
   - Exports MARKET and STATUS JSON.
   - Reads COMMAND JSON.
   - Applies OPEN, MODIFY, and CLOSE with MT4 trade functions.
   - Writes ACK JSON and archive markers.
   - Contains no strategy logic.

3. **Runtime files**
   - `runtime/history/history.json` - rolling candles.
   - `runtime/state.json` - engine state.
   - `runtime/audit.jsonl` - append-only cycle audit.
   - `runtime/metrics.json` - observability output.
   - `runtime/bridge/` - MT4 JSON protocol directories.
   - `runtime/STOP_TRADING` - operator stop sentinel.

## Data flow

```text
MT4 broker feed
  -> CHECK_SYSTEM_V3.mq4
  -> MARKET/STATUS JSON
  -> Python engine
  -> regime/strategy/risk/management
  -> COMMAND JSON
  -> CHECK_SYSTEM_V3.mq4
  -> MT4 OrderSend/OrderModify/OrderClose
  -> ACK JSON
  -> Python reconciliation/audit
```

## Invariants

- Protocol version is `3.0.0`.
- MT4 is not allowed to decide entries, exits, sizing, or risk.
- Commands must carry stable `command_id` values.
- The bridge writes JSON atomically with a temp file and replace operation.
- Live trading requires explicit configuration and MT4 operator enablement.

## Configuration

`config/system.example.json` documents the v3 defaults. The config model rejects unknown fields and requires:

- `version = "3.0.0"`
- `protocol_version = "3.0.0"`
- `runtime.protocol_version = "3.0.0"`
- `position.default_lot == position_sizing.fixed_lot`

## Failure handling

The Python process should treat missing/stale market data, missing ACKs, broker rejections, risk blocks, and stop sentinels as explicit operational states. Operators should inspect audit logs, ACK files, and MT4 Journal/Experts logs before resuming live operation.
