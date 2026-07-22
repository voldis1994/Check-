# MT4 Protocol 3.0.0

The CHECK SYSTEM v3 bridge uses atomic JSON files. MT4 exports MARKET and STATUS, consumes COMMAND, and emits ACK.

## Version

Every message must include:

```json
{
  "protocol_version": "3.0.0",
  "message_type": "MARKET"
}
```

Supported message types:

- `MARKET`
- `STATUS`
- `COMMAND`
- `ACK`

## Bridge layout

With default MT4 `BridgeRootPath = ""`, the root resolves to:

```text
TerminalDataPath\MQL4\Files\CHECK_SYSTEM
```

The v3 layout under the root is:

```text
runtime\bridge\
  market\
  status\
  commands\
  acknowledgements\
  archive\
```

## Atomic write rule

Writers create a temporary file in the destination directory and then replace the final path. The MT4 bridge uses `MoveFileExW` with replace and write-through flags.

Readers should ignore temporary files and only process `*.json` final files.

## MARKET

MT4 writes MARKET files under `runtime\bridge\market`.

Required fields exported by the v3 EA include:

```json
{
  "protocol_version": "3.0.0",
  "message_type": "MARKET",
  "message_id": "MARKET-...",
  "generated_at_utc": "2026-07-22T15:26:00Z",
  "sequence": 1,
  "account_number": 123456,
  "server": "Broker-Server",
  "symbol": "XAUUSD",
  "digits": 2,
  "point": 0.01,
  "tick_size": 0.01,
  "tick_value": 1.0,
  "bid": 2400.00,
  "ask": 2400.10,
  "spread": 10,
  "stop_level": 0,
  "freeze_level": 0,
  "min_lot": 0.01,
  "max_lot": 100.0,
  "lot_step": 0.01,
  "bars_m1": [],
  "market_open": true
}
```

`bars_m1` contains closed M1 bars only. The EA exports up to 3000 recent closed M1 bars when available.

## STATUS

MT4 writes STATUS files under `runtime\bridge\status`.

STATUS includes account identity, balance/equity/margin fields, connectivity, trade permission flags, the configured magic number, and current open positions.

Position fields include:

- `position_id`
- `ticket`
- `symbol`
- `side`
- `lot`
- `entry_price`
- `stop_loss`
- `take_profit`
- `open_time`
- `current_price`
- `profit`
- `magic_number`
- `owned_by_ea`

## COMMAND

Python writes COMMAND files under `runtime\bridge\commands`.

The MT4 bridge accepts:

- `OPEN`
- `MODIFY`
- `CLOSE`

Each command must have a stable `command_id`. The EA writes `archive\processed_<command_id>.json` after handling a command and will not re-execute a command with the same ID.

Example OPEN:

```json
{
  "protocol_version": "3.0.0",
  "message_type": "COMMAND",
  "command_id": "abc123",
  "action": "OPEN",
  "symbol": "XAUUSD",
  "side": "LONG",
  "lot": 0.01,
  "stop_loss": 2390.00,
  "take_profit": 2420.00,
  "magic_number": 3003001,
  "slippage": 20
}
```

Example MODIFY:

```json
{
  "protocol_version": "3.0.0",
  "message_type": "COMMAND",
  "command_id": "abc124",
  "action": "MODIFY",
  "symbol": "XAUUSD",
  "position_id": "12345678",
  "stop_loss": 2401.00,
  "take_profit": 2420.00
}
```

Example CLOSE:

```json
{
  "protocol_version": "3.0.0",
  "message_type": "COMMAND",
  "command_id": "abc125",
  "action": "CLOSE",
  "symbol": "XAUUSD",
  "position_id": "12345678",
  "close_fraction": 1.0
}
```

## ACK

MT4 writes ACK files under `runtime\bridge\acknowledgements`.

ACK fields include:

- `command_id`
- `success`
- `accepted`
- `reject`
- `ticket`
- `broker_order_id`
- `broker_error`
- `broker_error_message`
- `message`
- `applied.price`
- `applied.stop_loss`
- `applied.take_profit`
- `applied.lots`

Rejected broker operations are represented as ACK messages with `success = false`, `reject = true`, and broker error details.
