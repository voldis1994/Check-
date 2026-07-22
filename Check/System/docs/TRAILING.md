# Trailing

Protective management uses **ATR price distances** and a money-based breakeven lock. Lot size stays `0.01`.

## Flow

```
OPEN (fixed_lot 0.01)
→ favorable move ≥ be_activation_atr × ATR
→ BE SL so theoretical fill ≈ +be_net_profit_money (default +0.20)
→ after BE: ATR grid / distance trail
→ SL only improves (BUY: new_sl > broker_sl; SELL: new_sl < broker_sl)
```

## Config

```json
"trade_management": {
  "be_activation_r": null,
  "be_activation_atr": 0.60,
  "be_net_profit_money": 0.20,
  "trailing_activation_atr": 0.70,
  "trailing_distance_atr": 0.80,
  "trailing_step_atr": 0.20
}
```

- `be_activation_r` must be `null` (no account-risk R sizing)
- ATR is a **price-move unit**, not a risk-percent unit

## Breakeven (+0.20)

BE price uses `entry`, `side`, `fixed_lot`, `tick_size`, `tick_value`, `commission`, `swap`.  
Natural Gas vs Forex produce different BE prices; target net remains ≈ `+0.20`.

## ATR → price

Example: `ATR = 0.050`, `trailing_step_atr = 0.20` → step `0.010`, then round to broker `tick_size`.

Same path for `trailing_distance_atr` and activation thresholds.

## Never worsen

- BUY: `new_sl > broker_sl`
- SELL: `new_sl < broker_sl`
