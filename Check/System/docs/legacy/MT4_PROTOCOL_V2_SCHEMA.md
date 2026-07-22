# MT4 Protocol V2 Schema (draft → implemented in docs/MT4_PROTOCOL.md)

## Envelope (all messages)

```json
{
  "protocol_version": "2.0.0",
  "message_type": "market_snapshot|status_snapshot|command|acknowledgement",
  "message_id": "uuid",
  "generated_at_utc": "2026-07-22T12:00:00.000Z",
  "source": "mt4|python",
  "sequence": 1
}
```

## Directories

```
runtime/bridge/market/
runtime/bridge/status/
runtime/bridge/commands/
runtime/bridge/acknowledgements/
runtime/bridge/archive/
```

## Naming

- Command: `{sequence}_{command_id}.json`
- ACK: `{sequence}_{command_id}.ack.json`

## OPEN command (core fields)

`command_id`, `action=OPEN`, `symbol`, `magic`, `side`, `volume`, `requested_price`, `stop_loss`, `take_profit`, `slippage_points`, `setup_id`, `setup_fingerprint`, `created_at_utc`

## MODIFY command

`command_id`, `action=MODIFY`, `ticket`, `symbol`, `magic`, `requested_stop_loss`, `requested_take_profit`, `previous_broker_stop_loss`, `trailing_reason`, `trailing_step`, `created_at_utc`

## CLOSE command

`command_id`, `action=CLOSE`, `ticket`, `symbol`, `magic`, `volume`, `requested_price`, `close_reason`, `created_at_utc`

## ACK

Always includes requested vs applied price/SL/TP/volume when applicable, plus `broker_error_code`, `broker_error_text`, `processed_at_utc`, `status` ∈ {ACCEPTED mapped to SUCCESS semantics, REJECTED, FAILED, TIMEOUT handled by Python}.

## MODIFY success rule

`OrderModify==true` ∧ re-`OrderSelect` ∧ applied SL improves protection ∧ `|applied-requested|<=tolerance`.
