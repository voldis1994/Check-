# Strategy

Trend pullback break: M15 context → M5 setup → M1 trigger.

Works on **any** MT4 instrument (Forex, Natural Gas, gold, indices, CFDs) using:

1. Fixed lot `0.01`
2. ATR price distances
3. Broker `tick_size` / `tick_value` / `point` / `digits` / stop & freeze levels

## Pullback (ATR band)

Distance from close to HMA must lie in `[pullback_min_atr, pullback_max_atr] × ATR`.

## Trigger buffer

`trigger_buffer_atr × ATR` → absolute price → round to `tick_size`.

## Stop

Structure invalidation ± one `tick_size`, then risk validates against `maximum_stop_atr × ATR` and broker stop/freeze levels.

No Forex pip assumptions in the strategy path.
