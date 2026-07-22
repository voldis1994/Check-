# Market Regimes

This document records the v3 regime formulas implemented by the Python engine. These are descriptive rules, not profit claims.

## 5.1 Inputs

Regime detection uses closed decision-timeframe candles. The current configuration defaults to M15 for decisions.

The detector first attempts trend detection, then range detection, then falls back to transition.

```text
trend_snapshot = detect_trend(bars) or detect_range(bars) or transition_snapshot(latest_indicators)
```

## 5.2 Indicator formulas

All formulas use closed candles.

### EMA

For period `p`, if fewer than `p` values are available, EMA is unavailable.

```text
EMA[p-1] = mean(close[0:p])
k = 2 / (p + 1)
EMA[i] = (close[i] - EMA[i-1]) * k + EMA[i-1]
```

### True range

For the first candle, true range uses the candle itself. For later candles:

```text
TR[i] = max(
  high[i] - low[i],
  abs(high[i] - close[i-1]),
  abs(low[i] - close[i-1])
)
```

### ATR

For period `p`, if fewer than `p` candles are available, ATR is unavailable.

```text
ATR[p-1] = mean(TR[0:p])
ATR[i] = ((ATR[i-1] * (p - 1)) + TR[i]) / p
```

### ADX, +DI, -DI

For period `p`, if fewer than `2p` candles are available, ADX is unavailable.

```text
up = high[i] - high[i-1]
down = low[i-1] - low[i]
+DM[i] = up   if up > down and up > 0 else 0
-DM[i] = down if down > up and down > 0 else 0
TR[i] = true range using close[i-1]
```

Initial smoothed values:

```text
smTR = sum(TR[1:p+1])
sm+DM = sum(+DM[1:p+1])
sm-DM = sum(-DM[1:p+1])
```

For each `i >= p`:

```text
if i > p:
  smTR = smTR - smTR / p + TR[i]
  sm+DM = sm+DM - sm+DM / p + +DM[i]
  sm-DM = sm-DM - sm-DM / p + -DM[i]

+DI[i] = 100 * sm+DM / smTR if smTR else 0
-DI[i] = 100 * sm-DM / smTR if smTR else 0
DX[i] = 100 * abs(+DI[i] - -DI[i]) / (+DI[i] + -DI[i]) if (+DI[i] + -DI[i]) else 0
```

Initial ADX:

```text
ADX[2p-1] = mean(DX[p:2p])
ADX[i] = ((ADX[i-1] * (p - 1)) + DX[i]) / p
```

## 5.3 Trend regime

Default parameters:

- `ema_fast_period = 20`
- `ema_slow_period = 50`
- `adx_period = 14`
- `atr_period = 14`
- `min_adx = 25.0`
- `min_ema_separation_atr = 0.25`
- `min_slope_points = 5.0`
- `confirmation_bars = 2`

Let:

```text
fast = EMA(close, ema_fast_period)
slow = EMA(close, ema_slow_period)
atr = ATR(atr_period)
adx = ADX(adx_period)
ema_separation_atr = abs(fast[-1] - slow[-1]) / atr[-1]
slope_index = len(fast) - confirmation_bars - 1
ema_slope_points = (fast[-1] - fast[slope_index]) / instrument.point
```

Trend detection is unavailable when any current indicator is unavailable, when `adx[-1] < min_adx`, when `ema_separation_atr < min_ema_separation_atr`, or when `slope_index < 0`.

TREND_UP:

```text
fast[-1] > slow[-1]
and ema_slope_points >= min_slope_points
```

TREND_DOWN:

```text
fast[-1] < slow[-1]
and ema_slope_points <= -min_slope_points
```

## 5.4 Range regime

Default parameters:

- `ema_fast_period = 20`
- `ema_slow_period = 50`
- `adx_period = 14`
- `atr_period = 14`
- `max_adx = 20.0`
- `max_ema_separation_atr = 0.20`
- `lookback_bars = 48`
- `min_touches = 2`
- `boundary_tolerance_atr = 0.25`

Range detection requires at least `lookback_bars` closed candles.

Let:

```text
fast = EMA(close, ema_fast_period)
slow = EMA(close, ema_slow_period)
atr = ATR(atr_period)
adx = ADX(adx_period)
ema_separation_atr = abs(fast[-1] - slow[-1]) / atr[-1]
window = bars[-lookback_bars:]
range_high = max(high in window)
range_low = min(low in window)
tolerance = boundary_tolerance_atr * atr[-1]
high_touches = count(b in window where range_high - b.high <= tolerance)
low_touches = count(b in window where b.low - range_low <= tolerance)
```

Range detection is unavailable when any current indicator is unavailable, when `adx[-1] > max_adx`, or when `ema_separation_atr > max_ema_separation_atr`.

RANGE:

```text
high_touches >= min_touches
and low_touches >= min_touches
```

The confidence value is:

```text
max(0, max_ema_separation_atr - ema_separation_atr)
```

## 5.5 Transition regime

If neither trend nor range is confirmed, the detector emits TRANSITION.

Default parameters:

- `hold_bars = 2`
- `min_bars_between_changes = 1`

Transition confidence is:

```text
1 / hold_bars
```
