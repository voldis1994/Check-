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

## Config

```json
"trade_management": {
  "trailing_step_pips": 3.0,
  "money_step_trailing": {
    "initial_locked_profit_money": 0.20
  }
}
```

`activation_profit_money` / `profit_step_money` / `lock_increment_money` are unchanged unless a technical reason requires it.

## BE+0.20 calculation

Uses entry, volume, tick_value, tick_size, commission, swap, side, digits.
Missing tick metadata → clear error (`BE_PLUS_MISSING_TICK_DATA`); BE is **not** marked complete.

## Pip steps after confirmed BE

EURUSD 5-digit: `3.0 pips = 0.00030` (not `0.00003`).
JPY 3-digit: `pip = point * 10` → `3.0 pips = 0.03`.

BUY only raises SL; SELL only lowers SL. Multi-step jumps allowed; never worsen.

## Confirmation

A step is confirmed only after successful MODIFY ACK (command id + ticket) and broker SL matching within tolerance. Rejected MODIFY keeps the pending level for retry and stores the broker error code.

## Dashboard / journal fields

Broker SL, computed BE+0.20 SL, last confirmed SL, next 3-pip target, current net, locked net, MODIFY status, broker error, trailing reason code.
