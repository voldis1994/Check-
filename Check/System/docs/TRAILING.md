# Protective trailing: BE+0.20 then 3.0-pip steps

## Desired flow

```
Initial SL
→ BE with net +0.20 (account currency)
→ next SL = confirmed SL ± 3.0 pips
→ next ± 3.0 pips
→ continues while price moves in profit
```

Incorrect: stop trailing after BE+0.20.
Incorrect: confirm trailing from Python's requested SL after a generic SUCCESS ACK.

## Config

```json
"trade_management": {
  "trailing_step_pips": 3.0,
  "money_step_trailing": {
    "initial_locked_profit_money": 0.20
  }
}
```

`activation_profit_money` / `profit_step_money` / `lock_increment_money` remain for pre-BE activation compatibility. After BE is confirmed they must **not** move protective SL.

## BE+0.20 calculation

Uses entry, volume, tick_value, tick_size, commission, swap, side, digits.
Missing tick metadata → clear error (`BE_PLUS_MISSING_TICK_DATA`); BE is **not** marked complete.

## Pip steps after confirmed BE

EURUSD 5-digit: `3.0 pips = 0.00030` (not `0.00003`).
JPY 3-digit: `pip = point * 10` → `3.0 pips = 0.03`.

BUY only raises SL; SELL only lowers SL. Multi-step jumps allowed; never worsen.
Technical trailing after BE is snapped to the nearest already-reached 3-pip grid level (never rounded toward an unreached protective level).

## Confirmation sources (required)

A step is confirmed only from broker truth:

1. **MODIFY ACK** with MT4 re-read `applied_stop_loss` after `OrderModify`, matching pending SL within tolerance, with full identity checks (`command_id`, `action=MODIFY`, ticket, symbol, magic).
2. **Status reconciliation** when the open status position ticket/symbol/magic match and `stop_loss` matches pending within tolerance.

Forbidden: `broker_sl=float(order_command.stop_loss)` as proof that the broker applied the SL.

SUCCESS ACK without usable `applied_stop_loss` (or with mismatch) → `TRAILING_ACK_SL_MISMATCH`: do not confirm BE, do not advance pip steps, keep pending, allow status reconciliation.

Rejected MODIFY keeps the pending level for retry and stores the broker error code.

## MODIFY ACK fields (after successful OrderModify)

```json
{
  "action": "MODIFY",
  "ticket": 10,
  "requested_stop_loss": 1.10020,
  "applied_stop_loss": 1.10020,
  "requested_take_profit": 0.0,
  "applied_take_profit": 0.0,
  "broker_error_code": 0,
  "status": "SUCCESS"
}
```

MT4 SUCCESS requires: `OrderModify` true, re-`OrderSelect` ok, applied SL improves protection, applied SL within tolerance of requested.

## Dashboard / journal fields

Broker SL, computed BE+0.20 SL, last confirmed SL, next pip target, current net, locked net, MODIFY status, broker error, trailing reason code.
