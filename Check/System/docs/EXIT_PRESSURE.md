# Exit pressure

Scores how urgently an open position should tighten protection or close. Implemented in `position_management/exit_pressure.py`. Config: `trade_management.exit_pressure`.

## Components (0–1 each)

| Component | Config weight (default) | Meaning |
|-----------|-------------------------|---------|
| **Pullback** | `pullback_weight` 0.3 | Giveback from peak net: `(peak - current) / |peak|` |
| **Speed** | `speed_weight` 0.2 | Recent M1 bodies shrinking and/or adverse progress |
| **Trend** | `trend_weight` 0.2 | HMA(21) rolling against the position |
| **Rejection** | `rejection_weight` 0.2 | Upper wick (BUY) / lower wick (SELL) as fraction of range |
| **Spread** | `spread_weight` 0.1 | Current spread vs median and vs trailing step |

`total = Σ (component × weight)`.

When `enabled` is false, pressure is zero and never drives CLOSE.

## Thresholds

| Threshold | Default | Effect |
|-----------|---------|--------|
| `tighten_threshold` | **0.45** | Prefer snapped grid / pressure SL candidate |
| `high_lock_threshold` | **0.70** | Prefer high-lock SL when active |
| `critical_threshold` | **0.85** | Candidate for market CLOSE |

## Critical CLOSE rules

Critical CLOSE fires only when **all** of:

1. `critical_close_enabled` is true
2. `total >= critical_threshold`
3. Count of non-spread components (`pullback`, `speed`, `trend`, `rejection`) with value ≥ **0.45** is ≥ `minimum_non_spread_confirmations_for_close` (default **3**)

This avoids closing solely because spread spiked.

Reason code: `EXIT_PRESSURE_CRITICAL`.

## Interaction with trailing

Pressure does not replace BE/grid confirmation rules. It only adds SL candidates (or CLOSE) after activation / BE path as selected by `choose_protective_action`. Final proposed SL must still **improve** protection vs broker SL within tolerance.
