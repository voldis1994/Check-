# Strategy — TREND_PULLBACK_BREAK

Single enabled setup in v2: **trend context → pullback → breakout trigger**.

Timeframes (from M1 bars aggregated in Python):

| Role | TF | Job |
|------|----|-----|
| Context | **M15** | Directional bias |
| Setup | **M5** | Pullback to trend + invalidation / trigger levels |
| Entry | **M1** | Break of trigger with buffer |

Config key: `strategy.enabled_setup = "trend_pullback_break"`.

## Closed bars only

When `use_closed_bars_only` is true (default), the latest M1/M5/M15 bars used for decisions must be `complete`. Incomplete bars → `DATA_INVALID` / `BAR_INCOMPLETE`.

## M15 bias

Requires enough structure (`minimum_structure_bars`) and HMA (`hma_period`, default 21):

- **BUY bias:** higher swing highs + higher swing lows, HMA rising, last close holding above recent swing low
- **SELL bias:** lower highs + lower lows, HMA falling, last close holding below recent swing high
- Otherwise → `NO_SIGNAL` (unclear context)

## M5 pullback

Using ATR (`atr_period`) and HMA on M5:

- Distance from close to HMA ≤ `pullback_atr_distance * ATR`
- BUY: M5 low tags/crosses at or below HMA; SELL: M5 high tags/crosses at or above HMA
- **Invalidation:** extreme of recent M5 lows (BUY) / highs (SELL)
- **Trigger:** prior M5 swing high (BUY) / low (SELL) — excludes the current M5 bar so M1 can break it

No pullback → `NO_SIGNAL`.

## M1 trigger

With `trigger_break_buffer_pips` (price buffer = buffer × `pip_size`):

- **BUY:** M1 close ≥ trigger + buffer **and** bullish candle (close > open)
- **SELL:** M1 close ≤ trigger − buffer **and** bearish candle

On trigger:

- Proposed entry = M1 close
- Proposed SL = invalidation ± 1 pip (beyond structure)
- Setup gets `setup_id` (UUID) and deterministic `setup_fingerprint`

## Setup identity / expiry

- Fingerprint binds symbol, type, direction, context/pullback structure ids, origin time, trigger, invalidation
- Known fingerprints in instance state block duplicate re-entry of the same setup
- `setup_expiry_bars`: complete M1 bars since origin; beyond limit → expired (no entry)

## Outcomes

| Result | Meaning |
|--------|---------|
| `ENTRY_BUY` / `ENTRY_SELL` | Armed setup triggered; hand to risk |
| `NO_SIGNAL` | No bias / pullback / break — idle is correct |
| `DATA_INVALID` | Missing or incomplete bars |

There is **no** mandatory post-trade cooldown in v2 — only setup identity and risk/account gates.
