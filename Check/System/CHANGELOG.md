# Changelog

All notable changes to CHECK SYSTEM are documented here.

## 2.0.0 — 2026-07-22

Full production release: clean Python + MT4 bridge under `src/checktrader/`.

### Run

```text
python -m checktrader --config config/local/system.json
```

Requires Python **3.12+**. MT4 EA: `mt4/Experts/CHECK_SYSTEM_V2.mq4`.

### Highlights

- **Fixed lot only:** `position_sizing.fixed_lot = 0.01` (no risk%, no auto lot resize)
- **Universal instruments:** Forex, Natural Gas, gold, indices via ATR + `tick_size` / `tick_value`
- **AUTO symbol:** `instrument.symbol = "AUTO"` follows the MT4 chart
- Strategy: `TREND_PULLBACK_BREAK` (M15 → M5 → M1)
- Protective management: BE net +0.20, ATR trailing grid, high-lock, exit pressure
- Atomic protocol **2.0.0** under `runtime/bridge/`
- Windows scripts: `install`, `start_live`, `stop`, `health`, `run_tests`

### Safety

- Unsupported broker lot → `FIXED_LOT_NOT_SUPPORTED` (never rewrite lot)
- Margin fail → `MARGIN_INSUFFICIENT_FOR_FIXED_LOT`
- Broker applied SL required to confirm trailing
- Kill switch: `runtime/STOP_TRADING`
- Technical operability ≠ profitability guarantee

## Legacy

Earlier 1.x releases remain available as GitHub tags (`v1.1.5`, …). v2 replaces the live path.
