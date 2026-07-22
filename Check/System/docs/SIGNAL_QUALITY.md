# Signal Quality Gates

Centralized BUY / SELL / WAIT gates that reduce M1 noise entries. Directional
components choose the side; market-quality components decide whether the market
is tradeable.

## Module

`engine/decision/signal_quality.py`

Called from `engine/decision/engine.py` after candidate scoring and before the
final decision is returned.

## What counts as “one setup”

In this project a **setup** is one directional market impulse anchored to a
stable structure identity, not a single candle:

| Field | Role |
|-------|------|
| `instrument` + `timeframe` | Market context |
| `direction` | BUY or SELL |
| `setup_type` | Derived from structure bias / BOS (`continuation_buy`, `bos_sell`, …) |
| `structure_id` | Deterministic SHA-256 fragment from bias, BOS flag, normalized swing high/low, breakout level, and origin |
| `setup_origin_timestamp` | Timestamp of the bar that formed the structural anchor (swing low for BUY, swing high for SELL) |
| normalized structure level | Support (BUY) or resistance (SELL), rounded to instrument digits — **not** the moving entry/close |

The current closed bar time is stored separately as `signal_candle_timestamp`.
While the structure anchor is unchanged across consecutive M1 bars, the setup
fingerprint stays identical even though `signal_candle_timestamp` advances.

Example:

```
bar 06:01  setup_origin=06:00  fingerprint=FP1  → first OPEN allowed
bar 06:02  setup_origin=06:00  fingerprint=FP1  → DUPLICATE_SIGNAL
bar 06:03  setup_origin=06:00  fingerprint=FP1  → DUPLICATE_SIGNAL
…
new lower swing → new structure_id / origin → fingerprint=FP2
```

Fingerprints use canonical string serialization + SHA-256 (never Python `hash()`).

## Config (`signal_quality` in `config/system.json`)

| Field | Default | Meaning |
|-------|---------|---------|
| `minimum_signal_score` | `0.65` | Winning directional score floor |
| `minimum_score_delta` | `0.15` | Absolute BUY/SELL score gap whenever both scores are finite |
| `minimum_market_quality` | `0.60` | Average of behavior / impact / context |
| `minimum_directional_confirmations` | `3` | Of momentum/trend/structure/pressure agreeing |
| `cooldown_bars_after_trade` | `3` | Bars to WAIT after WIN / BREAKEVEN / UNKNOWN |
| `cooldown_bars_after_loss` | `5` | Bars to WAIT after LOSS |
| `duplicate_signal_expiry_bars` | `10` | How long an OPEN fingerprint stays active |

If the section is omitted, parser/config load inserts the same defaults.

## Score delta

`score_delta = abs(buy_score - sell_score)` is always checked before allowing a
trade when both scores are finite numbers — **including** when the opposite
candidate is `invalid` for another filter. Invalidity of the opposite side is
not treated as directional clarity.

If a score is not finite, the gate returns `DATA_INVALID` rather than inventing
strength.

## Trade outcomes

| Outcome | Meaning | Cooldown |
|---------|---------|----------|
| `WIN` | Net result / R > 0 | `cooldown_bars_after_trade` |
| `LOSS` | Net result / R < 0 | `cooldown_bars_after_loss` |
| `BREAKEVEN` | Net result / R ≈ 0 | `cooldown_bars_after_trade` |
| `UNKNOWN` | PnL not known (e.g. ACK close without history) | `cooldown_bars_after_trade` |

`BREAKEVEN` and `UNKNOWN` are never stored as `WIN`.

## Cooldown bar counting

For `cooldown_bars_after_trade = 3` after a close on bar **T**:

| Bar | Remaining before check | Decision | After advance |
|-----|------------------------|----------|---------------|
| T+1 | 3 | WAIT | 2 |
| T+2 | 2 | WAIT | 1 |
| T+3 | 1 | WAIT | 0 |
| T+4 | 0 | allowed (if other gates pass) | 0 |

Decrement runs **once per unique closed-bar timestamp**, after the quality check
(`peek` then `advance`). Repeated processing of the same candle time does not
consume extra cooldown. Skipped bars still decrement once when the next unique
timestamp is seen.

Loss cooldown uses the same counting with `cooldown_bars_after_loss`.

## Gate order

1. Non-finite scores → `WAIT` / `DATA_INVALID`
2. Trade cooldown active → `WAIT` / `TRADE_COOLDOWN_ACTIVE`
3. Market quality below minimum → `WAIT` / `MARKET_QUALITY_TOO_LOW`
4. No valid BUY or SELL setup → `WAIT` / `NO_VALID_SETUP`
5. Winning score below minimum → `WAIT` / `SIGNAL_SCORE_BELOW_MINIMUM`
6. Score delta too small (both numeric scores) → `WAIT` / `SIGNAL_DELTA_TOO_SMALL`
7. Too few directional confirmations → `WAIT` / `INSUFFICIENT_DIRECTIONAL_CONFIRMATIONS`
8. Duplicate fingerprint still active → `WAIT` / `DUPLICATE_SIGNAL`
9. Otherwise → `BUY` or `SELL`

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
| `NEWS_DATA_UNAVAILABLE` | Replay/context: news calendar missing (not assumed low) |

## Runtime wiring

- After a successful OPEN ACK, `instance_state.register_signal_fingerprint(...)`
  stores the decision fingerprint for `duplicate_signal_expiry_bars`.
- On full trade close (ACK CLOSE or position sync / closed-trade reconcile),
  `register_trade_close(outcome=...)` starts cooldown (`LOSS` when net profit
  is known and negative; `WIN` when positive; `BREAKEVEN` at zero; otherwise
  `UNKNOWN`).
- Decision journal optional fields include `score_delta`, `winning_side`,
  `winning_score`, `market_quality_score`, `reason_code`, `confirmation_count`,
  `fingerprint`, `cooldown_bars_remaining`, `component_directions`.

## Live safety

`engine/risk/live_safety.py` warns when daily-loss or drawdown limits are
disabled. On a live account (default for `run_live`; set `SYSTEM_DEMO_ACCOUNT=1`
for demo), missing limits **block new OPEN entries** via
`LiveRuntime.live_safety_block_entries`.

## Replay V2 (stateful, no MT4)

```bash
cd Check/System
python tools/replay_signals.py --market tests/integration/fixtures/replay/noise_m1_eurusd.csv
python tools/replay_signals.py --market path/to/market.csv --config config/system.json --output-dir /tmp/replay_out --json
python tools/replay_signals.py --market path/to/market.csv --news-file path/to/news.json --signal-audit
```

### Execution model assumptions

- Decision uses only bars available at that step (growing window, no look-ahead).
- Entry fills on the **next** bar’s open ± half-spread ± slippage (never signal-bar close as fill).
- One simulated position per instrument.
- SL/TP monitored on subsequent closed bars; MFE/MAE tracked from those bars.
- Same-bar SL+TP conflict without lower timeframe: **worst case** (SL) by default.
- Commission subtracted from net; results also reported in R multiples.
- Session from candle timestamp + timezone; regime from past+current bars only.
- Without a news file: `NEWS_DATA_UNAVAILABLE` / `news_filter_disabled` — news risk is **not** assumed low.
- Never writes MT4 `control_*.json` / ACK files (`control_files_written=0`).

### Outputs (`--output-dir`)

1. `replay_summary.json` — totals, reason codes, expectancy, drawdown, splits
2. `replay_trades.jsonl` / `replay_trades.csv` — per-trade ledger
3. optional `replay_signal_audit.jsonl` — per evaluated bar (`--signal-audit`)

Ledger fields include trade id, fingerprint, side, setup type, signal/entry/exit
times and prices, SL/TP, exit reason, spread/slippage/commission, gross/net/R,
MFE/MAE, scores, market quality, confirmations.

### Known limitations

- M1-only intrabar path: SL+TP same bar uses the conservative conflict rule.
- No multi-position portfolio simulation.
- News calendar is optional and simplistic (windowed impact list).
- Replay does **not** claim profitability; it validates gates, state, and determinism.
- Live trading remains separate; this tool never sends broker commands.
