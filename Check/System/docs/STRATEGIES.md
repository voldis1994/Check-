# Strategies

CHECK SYSTEM v3 strategies operate on closed decision-timeframe candles and a regime snapshot. This document describes the implemented sections 8-10. It does not imply profitability.

## 8. Trend continuation

Default parameters:

- `enabled = true`
- `pullback_ema_period = 20`
- `swing_lookback = 2`
- `max_pullback_atr = 1.0`
- `min_close_beyond_ema_points = 2.0`
- `entry_buffer_points = 2.0`
- `stop_atr_multiplier = 1.5`
- `take_profit_rr = 2.0`
- `min_adx = 25.0`
- `require_regime_alignment = true`

The strategy skips unless enabled and, when alignment is required, regime is `TREND_UP` or `TREND_DOWN`.

Filters:

```text
len(bars) >= max(pullback_ema_period, trend.adx_period, trend.atr_period)
EMA(pullback_ema_period), ATR(trend.atr_period), and ADX(trend.adx_period) are available
ADX[-1] >= min_adx
```

Shared values:

```text
close_buffer = min_close_beyond_ema_points * point
allowance = max_pullback_atr * ATR[-1]
```

Long signal in `TREND_UP`:

```text
last.low <= EMA[-1] + allowance
last.close >= EMA[-1] + close_buffer
stop = min(last_swing_low.price if available else last.low,
           last.close - stop_atr_multiplier * ATR[-1])
entry = market.ask + entry_buffer_points * point
take_profit = entry + (entry - stop) * take_profit_rr
```

Short signal in `TREND_DOWN`:

```text
last.high >= EMA[-1] - allowance
last.close <= EMA[-1] - close_buffer
stop = max(last_swing_high.price if available else last.high,
           last.close + stop_atr_multiplier * ATR[-1])
entry = market.bid - entry_buffer_points * point
take_profit = entry - (stop - entry) * take_profit_rr
```

If no signal is present, the result is HOLD with `NO_TREND_PULLBACK_CONFIRMATION`.

## 9. Range reversion

Default parameters:

- `enabled = true`
- `lookback_bars = 48`
- `boundary_tolerance_atr = 0.25`
- `rejection_close_fraction = 0.60`
- `stop_buffer_atr = 0.50`
- `take_profit_fraction = 0.50`
- `min_range_atr = 1.50`
- `max_adx = 20.0`

The strategy skips unless enabled and regime is `RANGE`.

Filters:

```text
len(bars) >= lookback_bars
ATR(range.atr_period) and ADX(range.adx_period) are available
ADX[-1] <= max_adx
range_width = range_high - range_low
range_width >= min_range_atr * ATR[-1]
```

Shared values:

```text
window = bars[-lookback_bars:]
range_high = max(high in window)
range_low = min(low in window)
tolerance = boundary_tolerance_atr * ATR[-1]
location = (last.close - last.low) / (last.high - last.low)
```

When `last.high == last.low`, `location` is set to `rejection_close_fraction`.

Long signal:

```text
last.low <= range_low + tolerance
location >= rejection_close_fraction
entry = market.ask
stop = range_low - stop_buffer_atr * ATR[-1]
take_profit = range_low + range_width * take_profit_fraction
```

Short signal:

```text
last.high >= range_high - tolerance
location <= 1 - rejection_close_fraction
entry = market.bid
stop = range_high + stop_buffer_atr * ATR[-1]
take_profit = range_high - range_width * take_profit_fraction
```

If no signal is present, the result is HOLD with `NO_RANGE_BOUNDARY_REJECTION`.

## 10. Breakout

Default parameters:

- `enabled = true`
- `box_lookback_bars = 32`
- `min_box_atr = 1.0`
- `max_box_atr = 4.0`
- `breakout_buffer_atr = 0.10`
- `retest_required = true`
- `retest_tolerance_atr = 0.20`
- `stop_buffer_atr = 0.50`
- `take_profit_rr = 2.0`
- `setup_expiry_bars = 8`
- `min_adx = 20.0`

Filters:

```text
len(bars) >= box_lookback_bars + 1
ATR(trend.atr_period) and ADX(trend.adx_period) are available
ADX[-1] >= min_adx
```

Existing active breakout setups are checked first.

Long retest trigger:

```text
last.low <= setup.trigger_price + retest_tolerance_atr * ATR[-1]
last.close >= setup.trigger_price
entry = market.ask
```

Short retest trigger:

```text
last.high >= setup.trigger_price - retest_tolerance_atr * ATR[-1]
last.close <= setup.trigger_price
entry = market.bid
```

New setup box:

```text
box = bars[-(box_lookback_bars + 1):-1]
box_high = max(high in box)
box_low = min(low in box)
box_width = box_high - box_low
box_width_atr = box_width / ATR[-1]
```

The box is pending unless:

```text
min_box_atr <= box_width_atr <= max_box_atr
```

Breakout buffer:

```text
buffer = breakout_buffer_atr * ATR[-1]
```

Long breakout:

```text
last.close > box_high + buffer
entry = market.ask
stop = box_low - stop_buffer_atr * ATR[-1]
take_profit = entry + (entry - stop) * take_profit_rr
trigger_price = box_high
```

Short breakout:

```text
last.close < box_low - buffer
entry = market.bid
stop = box_high + stop_buffer_atr * ATR[-1]
take_profit = entry - (stop - entry) * take_profit_rr
trigger_price = box_low
```

When `retest_required = true`, the first breakout creates a waiting setup instead of an immediate command. The setup expires after:

```text
current_bar_time + timeframe_minutes(decision_timeframe) * setup_expiry_bars
```
