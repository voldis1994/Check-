# Risk

Risk approval lives in `risk/engine.py` (`approve_order`). Config block: `position_sizing`.

## Universal instruments

Same code path for Forex, Natural Gas, gold, indices, and other MT4 symbols.

Canonical broker fields:

- `tick_size`, `tick_value`, `digits`, `point`
- `stop_level_points`, `freeze_level_points`
- `minimum_lot`, `maximum_lot`, `lot_step`

ATR distances → absolute price → round to `tick_size` → check stop/freeze.

Do **not** use Forex pip assumptions for strategy, risk, or trailing.

## Sizing — fixed lot only

```json
"position_sizing": {
  "mode": "fixed_lot",
  "fixed_lot": 0.01,
  "allow_broker_lot_normalization": false
}
```

If the broker cannot trade exactly `0.01` → `FIXED_LOT_NOT_SUPPORTED` (no rewrite).  
Insufficient margin → `MARGIN_INSUFFICIENT_FOR_FIXED_LOT`.

## Symbol gate

Configured `instrument.symbol` must match the market snapshot symbol, otherwise `SYMBOL_MISMATCH`.

## Spread gate

Optional: `execution.maximum_spread_points` and/or `execution.maximum_spread_atr` block OPEN with `SPREAD_EXECUTION_BLOCKED`.
