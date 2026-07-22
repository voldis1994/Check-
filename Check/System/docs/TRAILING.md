# Trailing — BE+0.20 then 3-pip grid

Protective stop management after an open position. Config under `trade_management`.

## Desired flow

```
Initial SL
→ activation (net / peak ≥ activation_profit_money)
→ BE with net +0.20 (account currency)  [be_net_profit_money]
→ confirm BE from broker applied SL
→ next SL = confirmed BE ± 3.0 pips (trailing_step_pips)
→ next ± 3.0 pips while price continues in profit
```

Incorrect: stop trailing after BE.  
Incorrect: confirm from Python’s **requested** SL after a generic SUCCESS ACK.

## Activation

Trailing waits until `current_net_profit` or `peak_net_profit` reaches `activation_profit_money` (default 0.5). Until then: `TRAILING_WAITING_ACTIVATION`.

## BE +0.20

Uses entry, volume, tick_value, tick_size, commission, swap, side, digits.

- Required net lock = `be_net_profit_money` (default **0.20**)
- Missing tick metadata → `BE_PRICE_METADATA_MISSING`; BE is **not** marked complete

BUY only raises SL; SELL only lowers SL.

## 3-pip grid after confirmed BE

- EURUSD 5-digit: `3.0 pips = 0.00030` (not `0.00003`)
- JPY-style: `pip_size = point * 10` → `3.0 pips = 0.03`
- Multi-step jumps allowed when price has already traveled; never worsen protection
- Pressure tighten snaps to the nearest **already-reached** grid level (never toward an unreached level)

Respect broker `stop_level` / `freeze_level` distances.

## Confirmation rules (required)

A BE or grid step is confirmed only from broker truth:

1. **MODIFY ACK** — after `OrderModify`, re-read `applied_stop_loss` matches pending SL within tolerance, with identity checks (`command_id`, `action=MODIFY`, ticket, symbol, magic). Status must be SUCCESS/ACCEPTED.
2. **Status reconciliation** — open position ticket/symbol/magic match and status `stop_loss` matches pending within tolerance.

**Forbidden:** treating `requested_stop_loss` (or copying it into a broker_sl field) as proof the broker applied the level.

If SUCCESS ACK lacks usable `applied_stop_loss` or it mismatches → `TRAILING_ACK_SL_MISMATCH`: do not confirm BE, do not advance grid, keep pending, allow status reconciliation.

Rejected MODIFY keeps the pending level for retry and records `broker_error_code`.

## High lock / exit pressure

After BE is confirmed, high-lock and exit-pressure candidates may compete; the engine picks the most protective improving SL (or CLOSE on critical pressure). See `docs/EXIT_PRESSURE.md`.

## Dashboard fields

Broker SL, calculated BE SL, confirmed BE SL, grid step/SL, pending SL, peak/current net, confirmation source, last reason code.
