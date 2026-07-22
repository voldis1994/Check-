# Strategy

Trend pullback break: M15 context → M5 setup → M1 trigger.

## Pullback (ATR band)

Distance from close to HMA must lie in:

`[pullback_min_atr, pullback_max_atr] × ATR`

BUY also requires `low ≤ HMA`; SELL requires `high ≥ HMA`.

## Trigger buffer

`trigger_buffer_atr × ATR` is converted to absolute price and rounded to `tick_size` (no Forex pip assumption).

## Stop loss proposal

Structure invalidation ± one `tick_size`, then risk engine validates against `maximum_stop_atr × ATR`, stop/freeze levels, and fixed lot `0.01`.

## Universality

Forex, Natural Gas, gold, indices use the same ATR + broker-spec path (`tick_size`, `tick_value`, `digits`, `point`, `stop_level`, `freeze_level`, lot bounds).
