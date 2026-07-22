# Trade Management

Trade management evaluates existing positions and may request CLOSE or MODIFY commands. It does not make MT4-side strategy decisions.

## Evaluation order

For each position, v3 checks close actions before stop-modification actions:

1. Stop hit.
2. Take profit hit.
3. Regime flip exit.
4. Breakeven move.
5. Trailing move.

If none applies, the result is HOLD with `MANAGEMENT_NO_ACTION`.

## Price side

For management calculations:

```text
price = bid for LONG
price = ask for SHORT
```

## Stop hit

Long:

```text
position.stop_loss is not None
and bid <= position.stop_loss
```

Short:

```text
position.stop_loss is not None
and ask >= position.stop_loss
```

The action is CLOSE with `close_fraction = 1.0`.

## Take profit hit

Long:

```text
position.take_profit is not None
and bid >= position.take_profit
```

Short:

```text
position.take_profit is not None
and ask <= position.take_profit
```

The action is CLOSE with `close_fraction = 1.0`.

## Regime flip exit

Regime flip exits are disabled when `management.exit_on_regime_flip` is false or the position strategy is `RANGE_REVERSION`.

Long:

```text
regime == TREND_DOWN
```

Short:

```text
regime == TREND_UP
```

The action is CLOSE with `close_fraction = 1.0`.

## Profit in R

For breakeven and trailing:

```text
risk_per_unit = abs(entry_price - stop_loss)
move = price - entry_price          for LONG
move = entry_price - price          for SHORT
profit_r = move / risk_per_unit
```

If no stop loss exists, `profit_r` is unavailable.

## Breakeven

Default parameters:

- `breakeven_trigger_rr = 1.0`
- `breakeven_offset_points = 2.0`

Breakeven is considered when:

```text
profit_r >= breakeven_trigger_rr
```

Target stop:

```text
LONG:  entry_price + breakeven_offset_points * point
SHORT: entry_price - breakeven_offset_points * point
```

The action is MODIFY only if the target improves the current stop.

## Trailing

Default parameters:

- `trailing_start_rr = 1.5`
- `trend_trailing_atr_multiplier = 1.0`
- `breakout_trailing_atr_multiplier = 1.2`
- `range_trailing_atr_multiplier = 0.8`

Trailing is considered when ATR is available and:

```text
profit_r >= trailing_start_rr
```

Multiplier selection:

```text
BREAKOUT strategy -> breakout_trailing_atr_multiplier
RANGE_REVERSION strategy or RANGE regime -> range_trailing_atr_multiplier
otherwise -> trend_trailing_atr_multiplier
```

Candidate stop:

```text
LONG:  price - multiplier * ATR
SHORT: price + multiplier * ATR
```

The action is MODIFY only if the candidate improves the current stop.
