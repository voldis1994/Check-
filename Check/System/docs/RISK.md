# Risk

Risk approval lives in `risk/engine.py` (`approve_order`). Config block: `position_sizing`.

## Sizing — fixed lot only

Production uses **only**:

```json
"position_sizing": {
  "mode": "fixed_lot",
  "fixed_lot": 0.01,
  "allow_broker_lot_normalization": false
}
```

- Volume is always exactly `fixed_lot` (default `0.01`)
- Equity, balance, SL distance, ATR, loss streaks, and daily PnL **never** change lot size
- Broker lot normalization is forbidden — if `0.01` is not allowed, the order is rejected

### Broker lot gate

If the broker cannot trade exactly `fixed_lot`:

| Condition | Result |
|-----------|--------|
| `fixed_lot < minimum_lot` | `FIXED_LOT_NOT_SUPPORTED` |
| `fixed_lot > maximum_lot` | `FIXED_LOT_NOT_SUPPORTED` |
| `fixed_lot` not aligned to `lot_step` | `FIXED_LOT_NOT_SUPPORTED` |

Logged fields: `requested_lot`, `minimum_lot`, `maximum_lot`, `lot_step`, `symbol`, `broker_server`.

The system never silently opens `minimum_lot`, `0.10`, or any other size.

## Stop loss (ATR, not pips)

- BUY: SL below entry; SELL: above entry
- Distance must be ≤ `maximum_stop_atr * ATR` (tick-rounded)
- Must respect broker `stop_level` / `freeze_level`
- ATR distance → absolute price → round to `tick_size` → validate levels

Take-profit (optional): `minimum_reward_risk` × SL distance when `fixed_take_profit_enabled`.

## Margin

If free margin is insufficient for the exact fixed lot → `MARGIN_INSUFFICIENT_FOR_FIXED_LOT`.  
Lot is **not** reduced.

## Not used in production

These must not participate in OPEN decisions:

- `risk_percent` / equity or balance percentage sizing
- daily loss / profit limits
- drawdown limits
- consecutive-loss limits
- cooldowns after loss or trade
- martingale / anti-martingale / dynamic position sizing

## Live gates outside risk

Account allow-list, expert enabled, trade allowed, freshness, kill switch, and max open positions are enforced in the application cycle — not by rewriting the lot.
