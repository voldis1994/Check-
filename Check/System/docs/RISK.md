# Risk

Risk approval lives in `risk/engine.py` (`approve_order`). Config block: `risk`.

## Sizing modes

### `fixed_lot`

- Volume = `risk.fixed_lot` (e.g. `0.01`)
- No equity-based scaling

### `risk_percent`

- Risk money = `equity * risk_percent / 100`
- Raw volume = risk_money / (SL distance × money-per-price-unit at 1.0 lot)
- Requires valid tick_value / tick_size

Unknown / invalid mode or missing percent → reject with a clear reason (no silent fallback to another mode).

## Stop loss

- Required when `require_stop_loss` is true
- BUY: SL must be below entry; SELL: above entry
- Distance in pips must be &gt; 0 and ≤ `maximum_stop_loss_pips`
- Take-profit distance defaults to `minimum_reward_risk` × SL distance when TP is computed for the order

## Lot bounds — no silent normalize

Default: `allow_lot_normalization: false`.

| Condition | Behavior |
|-----------|----------|
| Volume &lt; `minimum_lot` or &gt; `maximum_lot` | `INVALID_VOLUME` — reject |
| Volume not aligned to `lot_step` | `INVALID_VOLUME` — reject (**no rounding**) |
| `allow_lot_normalization: true` | Round to nearest `lot_step`, then re-check bounds |

Silent rounding of odd lots is intentionally **disabled** so misconfigured risk does not open unintended size.

## Margin

If `free_margin <= 0` → `MARGIN_INSUFFICIENT`.  
Insufficient tick specs → `SYMBOL_SPEC_MISSING`. Invalid prices → `PRICE_INVALID`.

## Live gates outside risk

Account allow-list, expert enabled, trade allowed, freshness, kill switch, and max open positions are enforced in the application cycle before/around risk — not by silently rewriting the lot.
