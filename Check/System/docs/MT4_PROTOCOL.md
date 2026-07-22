# MT4 Protocol 2.0.0

File bridge between MetaTrader 4 (`mt4/Experts/CHECK_SYSTEM_V2.mq4`) and Python (`checktrader`).

## Envelope (all messages)

| Field | Type | Notes |
|-------|------|-------|
| `protocol_version` | string | Always `"2.0.0"` |
| `message_type` | string | `market_snapshot` \| `status_snapshot` \| `command` \| `acknowledgement` |
| `message_id` | string | UUID |
| `generated_at_utc` | string | ISO-8601 UTC ending with `Z` |
| `source` | string | `mt4` or `python` |
| `sequence` | int | Monotonic per side / command stream |

## Directories

```
runtime/bridge/market/
runtime/bridge/status/
runtime/bridge/commands/
runtime/bridge/acknowledgements/
runtime/bridge/archive/
```

### Naming

| Kind | Pattern |
|------|---------|
| Market | `market_{SYMBOL}_{MAGIC}.json` |
| Status | `status_{ACCOUNT}.json` |
| Command | `{sequence}_{command_id}.json` |
| ACK | `{sequence}_{command_id}.ack.json` |

Writes are atomic (`*.tmp` then replace).

---

## MARKET (`market_snapshot`, source=`mt4`)

```json
{
  "protocol_version": "2.0.0",
  "message_type": "market_snapshot",
  "message_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "generated_at_utc": "2026-07-22T12:00:00.000Z",
  "source": "mt4",
  "sequence": 42,
  "account_number": "123456",
  "server": "Broker-Demo",
  "symbol": "EURUSD",
  "digits": 5,
  "point": 0.00001,
  "pip_size": 0.0001,
  "bid": 1.08512,
  "ask": 1.08516,
  "spread_points": 4,
  "spread_pips": 0.4,
  "tick_size": 0.00001,
  "tick_value": 1.0,
  "minimum_lot": 0.01,
  "maximum_lot": 100.0,
  "lot_step": 0.01,
  "stop_level_points": 10,
  "freeze_level_points": 0,
  "trade_allowed": true,
  "market_open": true,
  "bars_m1": [
    {
      "open_time_utc": "2026-07-22T11:58:00.000Z",
      "close_time_utc": "2026-07-22T11:59:00.000Z",
      "open": 1.08490,
      "high": 1.08520,
      "low": 1.08480,
      "close": 1.08510,
      "tick_volume": 120,
      "complete": true
    }
  ]
}
```

`bars_m1` must be closed bars (`complete: true`). Python aggregates M5/M15 from M1.

---

## STATUS (`status_snapshot`, source=`mt4`)

```json
{
  "protocol_version": "2.0.0",
  "message_type": "status_snapshot",
  "message_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "generated_at_utc": "2026-07-22T12:00:00.250Z",
  "source": "mt4",
  "sequence": 42,
  "account_number": "123456",
  "balance": 10000.0,
  "equity": 10012.5,
  "margin": 33.0,
  "free_margin": 9979.5,
  "margin_level": 30340.9,
  "trade_allowed": true,
  "expert_enabled": true,
  "positions": [
    {
      "ticket": 987654,
      "symbol": "EURUSD",
      "magic": 19942026,
      "side": "BUY",
      "volume": 0.01,
      "open_time": "2026-07-22T11:55:12.000Z",
      "open_price": 1.08450,
      "stop_loss": 1.08380,
      "take_profit": 0.0,
      "current_price": 1.08512,
      "profit": 6.2,
      "swap": 0.0,
      "commission": -0.07,
      "net_profit": 6.13,
      "comment": "CHECK_V2"
    }
  ]
}
```

`positions` (alias `open_positions`) may be empty when flat.

---

## OPEN command (source=`python`)

```json
{
  "protocol_version": "2.0.0",
  "message_type": "command",
  "message_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "generated_at_utc": "2026-07-22T12:00:01.000Z",
  "source": "python",
  "sequence": 7,
  "command_id": "cmd-open-001",
  "action": "OPEN",
  "symbol": "EURUSD",
  "magic": 19942026,
  "side": "BUY",
  "volume": 0.01,
  "requested_price": 1.08516,
  "stop_loss": 1.08380,
  "take_profit": 1.08720,
  "slippage_points": 20,
  "setup_id": "setup-uuid",
  "setup_fingerprint": "sha256:...",
  "created_at_utc": "2026-07-22T12:00:01.000Z"
}
```

Core fields: `command_id`, `action=OPEN`, `symbol`, `magic`, `side`, `volume`, `requested_price`, `stop_loss`, `take_profit`, `slippage_points`, `setup_id`, `setup_fingerprint`, `created_at_utc`.

---

## MODIFY command

```json
{
  "protocol_version": "2.0.0",
  "message_type": "command",
  "message_id": "d4e5f6a7-b8c9-0123-def0-234567890123",
  "generated_at_utc": "2026-07-22T12:05:00.000Z",
  "source": "python",
  "sequence": 8,
  "command_id": "cmd-mod-002",
  "action": "MODIFY",
  "symbol": "EURUSD",
  "magic": 19942026,
  "ticket": 987654,
  "requested_stop_loss": 1.08470,
  "requested_take_profit": 0.0,
  "previous_broker_stop_loss": 1.08380,
  "trailing_reason": "BE_CALCULATED",
  "trailing_step": 0,
  "created_at_utc": "2026-07-22T12:05:00.000Z"
}
```

---

## CLOSE command

```json
{
  "protocol_version": "2.0.0",
  "message_type": "command",
  "message_id": "e5f6a7b8-c9d0-1234-ef01-345678901234",
  "generated_at_utc": "2026-07-22T12:10:00.000Z",
  "source": "python",
  "sequence": 9,
  "command_id": "cmd-close-003",
  "action": "CLOSE",
  "symbol": "EURUSD",
  "magic": 19942026,
  "ticket": 987654,
  "volume": 0.01,
  "requested_price": 1.08550,
  "close_reason": "EXIT_PRESSURE_CRITICAL",
  "created_at_utc": "2026-07-22T12:10:00.000Z"
}
```

---

## ACK (`acknowledgement`, source=`mt4`)

Always include requested vs applied price/SL/TP/volume when applicable, plus broker error fields.

```json
{
  "protocol_version": "2.0.0",
  "message_type": "acknowledgement",
  "message_id": "f6a7b8c9-d0e1-2345-f012-456789012345",
  "generated_at_utc": "2026-07-22T12:05:00.400Z",
  "source": "mt4",
  "sequence": 8,
  "command_id": "cmd-mod-002",
  "action": "MODIFY",
  "status": "SUCCESS",
  "symbol": "EURUSD",
  "magic": 19942026,
  "ticket": 987654,
  "requested_stop_loss": 1.08470,
  "applied_stop_loss": 1.08470,
  "requested_take_profit": 0.0,
  "applied_take_profit": 0.0,
  "broker_error_code": 0,
  "broker_error_text": "",
  "processed_at_utc": "2026-07-22T12:05:00.350Z"
}
```

`status` ∈ {`SUCCESS` (mapped to ACCEPTED in Python), `REJECTED`, `FAILED`, `ALREADY_PROCESSED`, `ACCEPTED`}. Timeouts are detected by Python when ACK age exceeds `execution.ack_timeout_ms`.

### OPEN ACK fill fields

Include `requested_price` / `applied_price`, `requested_volume` / `applied_volume`, and `ticket`.

### MODIFY success rule (MT4)

`OrderModify == true` **and** re-`OrderSelect` **and** applied SL improves protection **and** `|applied - requested| <= tolerance`.

Python confirms trailing only when identity matches (`command_id`, action, ticket, symbol, magic) and applied SL matches pending within tolerance — or when status reconciliation shows the same.
