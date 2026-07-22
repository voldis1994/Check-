# Risk Management

Risk management validates a strategy signal before a command is written. It does not guarantee outcomes or prevent all losses.

## Defaults

- `runtime.mode = "paper"`
- `runtime.trading_enabled = false`
- `position.max_open_positions = 1`
- `position.allow_hedging = false`
- `position_sizing.method = "fixed_lot"`
- `position_sizing.fixed_lot = 0.01`
- `risk.min_stop_points = 50.0`
- `risk.max_stop_points = 5000.0`
- `risk.min_reward_risk = 1.20`
- `risk.max_slippage_points = 20.0`
- `spread.max_points = 30.0`
- `spread.max_atr_fraction = 0.10`
- `limits.max_daily_trades = 3`
- `limits.max_consecutive_losses = 2`
- `limits.cooldown_minutes = 30.0`

## Live safety

If `runtime.mode == "live"` and `runtime.trading_enabled` is false, the order is blocked with `RISK_LIVE_NOT_ENABLED`.

Account status blocks the order when:

```text
not connected
or not trading_allowed
or equity < account.min_equity
```

## Position limit

The order is blocked with `RISK_POSITION_EXISTS` when:

```text
len(open_positions) >= position.max_open_positions
```

## Fixed lot validation

Only fixed lot sizing is currently configured.

```text
lot = position_sizing.fixed_lot
```

The lot is invalid when:

```text
lot < min_lot
or lot > max_lot
or lot is not aligned to lot_step from min_lot
```

Lot-step alignment:

```text
steps = round((lot - min_lot) / lot_step)
normalized = min_lot + steps * lot_step
abs(normalized - lot) <= lot_step / 1000
```

## Spread validation

```text
spread_points = max(0, ask - bid) / point
```

The order is blocked when:

```text
spread_points > spread.max_points
```

If ATR is available:

```text
atr_points = ATR / point
spread_points > spread.max_atr_fraction * atr_points
```

## Stop-distance validation

```text
stop_distance_points = abs(entry_price - stop_loss) / point
minimum = max(risk.min_stop_points, symbol.stop_level_points)
```

The order is blocked when:

```text
stop_distance_points < minimum
or stop_distance_points > risk.max_stop_points
```

## Reward-risk validation

Signals without take profit pass this check. Otherwise:

```text
risk = abs(entry_price - stop_loss)
reward = abs(take_profit - entry_price)
reward / risk >= risk.min_reward_risk
```

Long orders must satisfy:

```text
stop_loss < entry_price < take_profit
```

Short orders must satisfy:

```text
take_profit < entry_price < stop_loss
```

## Daily limits and cooldown

The limit state resets on a new UTC date.

The order is blocked when:

```text
daily_trades >= limits.max_daily_trades
or consecutive_losses >= limits.max_consecutive_losses
or now < cooldown_until
```

When a trade opens, `daily_trades` increments. When a trade closes with negative profit, `consecutive_losses` increments and:

```text
cooldown_until = close_time + limits.cooldown_minutes
```

When a trade closes with non-negative profit, consecutive losses and cooldown are cleared.
