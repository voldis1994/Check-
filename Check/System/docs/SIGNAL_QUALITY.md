# Signal Quality Gates

Centralized BUY / SELL / WAIT gates that reduce M1 noise entries. Directional
components choose the side; market-quality components decide whether the market
is tradeable.

## Module

`engine/decision/signal_quality.py`

Called from `engine/decision/engine.py` after candidate scoring and before the
final decision is returned.

## Config (`signal_quality` in `config/system.json`)

| Field | Default | Meaning |
|-------|---------|---------|
| `minimum_signal_score` | `0.65` | Winning directional score floor |
| `minimum_score_delta` | `0.15` | Absolute BUY/SELL score gap when both valid |
| `minimum_market_quality` | `0.60` | Average of behavior / impact / context |
| `minimum_directional_confirmations` | `3` | Of momentum/trend/structure/pressure agreeing |
| `cooldown_bars_after_trade` | `3` | Bars to WAIT after any closed trade |
| `cooldown_bars_after_loss` | `5` | Bars to WAIT after a losing close |
| `duplicate_signal_expiry_bars` | `10` | How long an OPEN fingerprint stays active |

If the section is omitted, parser/config load inserts the same defaults.

## Gate order

1. Trade cooldown active → `WAIT` / `TRADE_COOLDOWN_ACTIVE`
2. Market quality below minimum → `WAIT` / `MARKET_QUALITY_TOO_LOW`
3. No valid BUY or SELL setup → `WAIT` / `NO_VALID_SETUP`
4. Winning score below minimum → `WAIT` / `SIGNAL_SCORE_BELOW_MINIMUM`
5. Score delta too small (both sides valid) → `WAIT` / `SIGNAL_DELTA_TOO_SMALL`
6. Too few directional confirmations → `WAIT` / `INSUFFICIENT_DIRECTIONAL_CONFIRMATIONS`
7. Duplicate fingerprint still active → `WAIT` / `DUPLICATE_SIGNAL`
8. Otherwise → `BUY` or `SELL`

## Reason codes

| Code | Description |
|------|-------------|
| `SIGNAL_SCORE_BELOW_MINIMUM` | Winning directional score below floor |
| `SIGNAL_DELTA_TOO_SMALL` | BUY/SELL gap below `minimum_score_delta` |
| `MARKET_QUALITY_TOO_LOW` | Shared quality below floor |
| `INSUFFICIENT_DIRECTIONAL_CONFIRMATIONS` | Fewer than N components agree |
| `TRADE_COOLDOWN_ACTIVE` | Post-trade bar cooldown |
| `DUPLICATE_SIGNAL` | Same setup fingerprint still active |
| `NO_VALID_SETUP` | Neither BUY nor SELL candidate valid |

## Runtime wiring

- After a successful OPEN ACK, `instance_state.register_signal_fingerprint(...)`
  stores the decision fingerprint for `duplicate_signal_expiry_bars`.
- On full trade close (ACK CLOSE or position sync / closed-trade reconcile),
  `register_trade_close(...)` starts cooldown bars (`was_loss` when net profit
  is known and negative; otherwise `False`).
- Decision journal optional fields include `score_delta`, `winning_side`,
  `winning_score`, `market_quality_score`, `reason_code`, `confirmation_count`,
  `fingerprint`, `cooldown_bars_remaining`, `component_directions`.

## Live safety

`engine/risk/live_safety.py` warns when daily-loss or drawdown limits are
disabled. On a live account (default for `run_live`; set `SYSTEM_DEMO_ACCOUNT=1`
for demo), missing limits **block new OPEN entries** via
`LiveRuntime.live_safety_block_entries`.

## Replay (no MT4)

```bash
cd Check/System
python tools/replay_signals.py --market tests/integration/fixtures/market_EURUSD_100001.csv
python tools/replay_signals.py --market path/to/market_EURUSD_100001.csv --config config/system.json
```

Feeds a growing bar window into `run_decision_engine` chronologically and prints
BUY / SELL / WAIT / BLOCK counts plus reason-code tallies. Never writes control
or ACK files.
