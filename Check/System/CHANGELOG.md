# Changelog

All notable changes to CHECK SYSTEM are documented here.

## 2.0.0 — 2026-07-22

### Rewrite

Clean-architecture rewrite of the live Python + MT4 bridge. Package lives under `src/checktrader/`; entrypoint is `python -m checktrader`.

### Added

- Typed domain models (`domain/`) and Pydantic config (`config/`) with live account validation
- Atomic MT4 protocol **2.0.0** under `runtime/bridge/` (market, status, sequenced commands, ACK)
- Multi-timeframe strategy `TREND_PULLBACK_BREAK` (M15 → M5 → M1) with setup fingerprints
- Risk engine: `fixed_lot` / `risk_percent`, no silent lot normalization unless opted in
- Position management: BE net +0.20, 3-pip grid, high lock, exit pressure
- Execution outbox, ACK validation, broker reconciliation
- Persistent instance state with checksum + recovery path
- Local dashboard snapshot server + HTML template
- Windows ops scripts: `install`, `start_live`, `stop`, `health`, `run_tests`
- CLI tools: `inspect_bridge`, `validate_config`, `reconcile_account`, `export_audit`, `replay`
- Docs set: architecture, live operation, protocol, strategy, trailing, exit pressure, risk, troubleshooting
- CI scoped to v2 test directories with ruff / mypy / pytest

### Changed

- Broker applied SL is required to confirm trailing (ACK or status); requested SL alone is not proof
- Kill switch path standardized to `runtime/STOP_TRADING`
- Config for live accounts lives in gitignored `config/local/system.json` (seeded from example)

### Removed from the v2 design (legacy still on disk until cutover)

- Relative BUY/SELL score entry and mandatory trade cooldown
- AI advisory as a hard entry gate
- Overwrite-style control/ack files without sequence / message IDs
- M1-only analysis path for setup context

### Notes

- Legacy `engine/` and root `.bat` entrypoints remain until a separate deletion pass
- MetaEditor compile is Windows-only; Linux CI covers protocol shapes and Python logic
- Technical operability ≠ profitability guarantee
