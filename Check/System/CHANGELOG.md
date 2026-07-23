# Changelog

## v3.0.1

- Desktop control panel: `START_DASHBOARD.bat` / `tools/dashboard.py` — start paper/live, activity feed, stop, deploy MT4 (no web UI).
- Harden bridge market reader: skip invalid M1 bars (missing time) instead of crashing; ignore empty local bridge folders without market JSON.
- Fix MT4 bridge writes: FileOpen now uses paths relative to `MQL4\\Files` + FILE_ANSI so `latest.json` actually updates (stale bridge root cause).
- Fix `BARS_NOT_SEQUENTIAL` on real markets: allow session gaps (multiples of TF); use one freshest sticky bridge so two MT4 terminals do not corrupt shared history.
- Harden live path for NATURALGAS: partial M15 aggregation, heartbeat freshness (not M1 open age), broker GMT bar times, AUTO specs from bridge, clear `HISTORY_INSUFFICIENT m15=N/200` warm-up.
- Multi-account: every discovered MT4 bridge runs each cycle with isolated history/state/dedupe under `runtime/accounts/<id>/` (no more sticky single-account).
- Unblock trading: stop freezing on EMA200 warm-up; always reconcile/manage open broker trades; detect regime with available M15 (ema200 clamped).
- Modern desktop dashboard: Baltic signal-deck UI, dual-account panel, motion (brand underline + live pulse + activity flash).
- Pro dark console dashboard: sidebar accounts, metric cards, equity curve, bridge-health ring, quick actions, live trades + activity pages (real broker/audit data only).
- Shared market regime across multi-account: same symbol uses one regime from the richest M15 feed; thinner accounts get M1 history seeded so both are not stuck in different warm-up states.
- Breakout M1 impulse: staircase NATURALGAS moves that never print a clean M5 box+retest can OPEN on M1 range-break; TRANSITION also allows trend continuation.
- Loosen regime/strategy gates: soft TREND path (leave perpetual TRANSITION), breakout_only default, immediate M1 trend entries, wider range filters — stop pointless HOLD loops.
- Auto-sync: every start/load refreshes trading gates in `config/system.json` from shipped example (keeps live/runtime/account_id/paths).
- Disable RISK_ACCOUNT_NOT_OK by default; daily trade/loss/cooldown limits off (0); no min RR; force M1 entry when strategies would idle-HOLD.
- Default lot **0.02**; tighter stops (`force_stop_atr` 0.18, buffers 0.08); M1 impulse / breakout SL clamped under trigger candle (not lookback range).
- No hard TP by default (`hard_take_profit=false`): exits via trailing from ~0.35R + breakeven; management auto-synced.
- Symbol-aware entries: open trade on another symbol no longer freezes the new chart in perpetual `MANAGEMENT_NO_ACTION`; START LIVE auto-arms `trading_enabled`.

## v3.0.0

- Full rebuild from zero for CHECK SYSTEM v3 (not a partial port of v2).
- Python owns regime detection, strategy routing, setup lifecycle, risk checks, trade management, state, audit, and command generation.
- MT4 is reduced to a transport bridge that exports MARKET/STATUS JSON and applies COMMAND JSON with ACK output.
- Bridge paths aligned: `market/latest.json`, `status/latest.json`, `commands/`, `acknowledgements/`; parses `bars_m1`.
- Cycle audit carries regime, strategy, setup state, decision, reason code, human-readable reason, passed/failed conditions, indicator snapshot, risk and execution results.
- Live mode never silently falls back to paper market data; `STOP_TRADING` halts the loop.
- Protocol version is `3.0.0`.
- v2 is preserved in git tag `system-v2-final-backup` and branch `backup/system-v2-before-v3-rebuild`.
