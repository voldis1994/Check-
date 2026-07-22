# Changelog

## v3.0.1

- Desktop control panel: `START_DASHBOARD.bat` / `tools/dashboard.py` — start paper/live, activity feed, stop, deploy MT4 (no web UI).
- Harden bridge market reader: skip invalid M1 bars (missing time) instead of crashing; ignore empty local bridge folders without market JSON.

## v3.0.0

- Full rebuild from zero for CHECK SYSTEM v3 (not a partial port of v2).
- Python owns regime detection, strategy routing, setup lifecycle, risk checks, trade management, state, audit, and command generation.
- MT4 is reduced to a transport bridge that exports MARKET/STATUS JSON and applies COMMAND JSON with ACK output.
- Bridge paths aligned: `market/latest.json`, `status/latest.json`, `commands/`, `acknowledgements/`; parses `bars_m1`.
- Cycle audit carries regime, strategy, setup state, decision, reason code, human-readable reason, passed/failed conditions, indicator snapshot, risk and execution results.
- Live mode never silently falls back to paper market data; `STOP_TRADING` halts the loop.
- Protocol version is `3.0.0`.
- v2 is preserved in git tag `system-v2-final-backup` and branch `backup/system-v2-before-v3-rebuild`.
