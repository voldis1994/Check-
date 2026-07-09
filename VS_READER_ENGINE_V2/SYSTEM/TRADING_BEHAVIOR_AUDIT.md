# SYSTEM Trading Behavior Audit

**Date:** 2026-07-08  
**Scope:** End‑to‑end trading behavior from market data to MT4 orders  
**Mode:** Documentation only — no code changes

This document explains, as precisely as possible from the Python + MQL4 code and tests, how SYSTEM behaves in all major trading situations:

- When it opens **BUY**
- When it opens **SELL**
- When it returns **WAIT**
- When it returns **BLOCK**
- When it **closes** a trade (CLOSE)
- When it **changes SL/TP** (MODIFY)
- When it performs **partial close**
- When it **refuses to open** or re‑send an order
- How it reacts to **spread**, **stale data**, **risk limits**, **timeouts**, **recovery**, and **MT4 errors**

---

## 1. Full signal path: from market data to order

### 1.1 Data export from MT4 (MQL4 side)

**Key files:**
- `mql4/Experts/SYSTEM_EA.mq4`
- `mql4/Include/SYSTEM_Export.mqh`
- `mql4/Include/SYSTEM_Status.mqh`
- `mql4/Include/SYSTEM_Control.mqh`
- `mql4/Include/SYSTEM_Execution.mqh`
- Tests: `tests/mql4/test_system_*.py`

**Exported files (per account, symbol, magic):**

- **Market:**
  - Path: `data/clients/{account_id}/market_{symbol}_{magic}.csv`
  - Content: OHLCV M1 candles (`time_utc,open,high,low,close,volume,symbol,timeframe,digits,point`)

- **Sensor (spread & micro‑data):**
  - Path: `data/clients/{account_id}/sensor_{symbol}_{magic}.csv`
  - Content: tick‑like spread readings (`time_utc,bid,ask,spread,spread_points,symbol,digits,point`)

- **Status:**
  - Path: `data/clients/{account_id}/status_{account_id}.json`
  - Content (`StatusRecord`):
    - `schema_version`
    - `timestamp_utc`
    - `account_id`
    - `connected`
    - `trade_allowed`
    - `balance`, `equity`, `margin_free`, `ea_version`
    - `open_positions`: list of positions for this account (symbol + magic‑filtered in EA)

- **Universe:**
  - Paths:
    - Global: `data/universe/universe.json`
    - Per account: `data/clients/{account_id}/universe.json`
  - Content: context‑only fields (session, regime, impact news, etc.) — no trade signals allowed.

---

### 1.2 Loader → validator → normalizer → state

**Loader modules:**
- `engine/loader/market_loader.py`
- `engine/loader/sensor_loader.py`
- `engine/loader/status_loader.py`
- `engine/loader/universe_loader.py`
- Tests: `tests/loader/test_*_loader.py`

**Validators:**
- `engine/validator/market_validator.py`
- `engine/validator/sensor_validator.py`
- `engine/validator/status_validator.py`
- `engine/validator/universe_validator.py`
- Tests: `tests/loader/test_*_validator.py`

**Normalizers & state:**
- `engine/normalizer/market_normalizer.py`
- `engine/normalizer/instrument_params.py`
- `engine/normalizer/spread_model.py`
- `engine/state/instance_state.py`
- `engine/state/spread_state.py`
- `engine/state/memory.py`

**Path resolution:**
- `engine/core/paths.py` (`SystemPaths`):
  - `account_dir(account_id)`
  - `account_state_dir(account_id)` (`state/`)
  - `instance_history_dir(account_id,symbol,magic)` (`history/`)

**Pipeline per cycle (simplified; see `engine/core/cycle.py` and tests in `tests/core/test_cycle.py`):**

1. **Load market:**
   - `load_market_data(paths, instance, cache=...)` returns `RawMarketData` with:
     - `file_path`, `row_count`, `raw_text`, `modified_utc`
   - `validate_market_for_cycle(raw_market)`:
     - Returns `ValidationResult` (**INVALID**) with reasons (missing file, bad header, empty, etc.)
       → cycle logs error and **BLOCKS / ends** before decision.
     - Or returns tuple of `NormalizedMarketBar` if **VALID**.

2. **Load sensor:**
   - `load_sensor_data(paths, instance, cache=...)`  
   - `validate_sensor_for_cycle(raw_sensor)` → same pattern (INVALID vs normalized sensor reading).

3. **Load status:**
   - `load_status_data(paths, account_id, cache=...)`
   - `validate_status_for_cycle(raw_status)` ensures:
     - `schema_version` valid
     - `connected` is bool
     - `trade_allowed` bool
   - Converted to `StatusRecord` (`engine/protocol/models.py`).

4. **Load universe:**
   - `load_universe_data(paths, account_id, use_global_universe)` + `validate_universe_for_cycle`
   - Must be “context‑only” (no forbidden fields like `signal`, etc.).

5. **Normalize market & spread:**
   - `engine/normalizer/market_normalizer.py` builds `NormalizedMarketBar` list.
   - `engine/normalizer/spread_model.py` + `engine/state/spread_state.py` update spread model, history, relative spread.

6. **Update in‑memory state:**
   - `engine/state/instance_state.InstanceState`:
     - Tracks `last_decision`, `position_side`, `position_volume`, `position_bars_open`, `partial_close_applied`, `last_ack_status`, open ticket, SL/TP, etc.
   - `engine/state/memory.StateMemory`:
     - Holds `InstanceMemory` with:
       - `instance_state`
       - `spread_state`
       - `market_history` (M1 lookback)
       - `last_analysis_context`, `last_decision_result`

---

### 1.3 Analysis → Decision → Risk

**Analysis:**
- `engine/analysis/context.py` (`AnalysisContext`)
- `engine/analysis/engine.py` (`run_analysis_engine`)
- Individual modules: `momentum.py`, `trend/structure/pressure/behavior/impact.py`
- Tests: `tests/analysis/test_*.py`

**Decision:**
- `engine/decision/engine.py` (`run_decision_engine`)
- `engine/decision/buy.py`, `sell.py`, `candidate.py`, `scorer.py`
- Filters: `engine/decision/filters/*.py` (spread, volatility, news)
- WAIT/BLOCK: `engine/decision/wait_block.py`
- Tests: `tests/decision/test_*.py`

**Risk:**
- `engine/risk/engine.py` (`run_risk_engine`)
- `engine/risk/rules.py` (ALLOW/BLOCK)
- `engine/risk/position_sizing.py`
- `engine/risk/sl_tp.py` (stop‑loss / take‑profit validation)
- Tests: `tests/risk/test_*.py`

**High‑level flow (`run_decision_engine`):**

Input:
- `universe: UniverseRecord`
- `market_bars: tuple[NormalizedMarketBar, ...]`
- `instance_state: InstanceState`
- `relative_spread: float`
- `system_config: SystemConfig`
- `block_reason: str | None`
- `execution_possible: bool`

Steps:
1. Run **AnalysisEngine**:
   - `run_analysis_engine(universe, market_bars)`
   - Compute context scores (momentum, trend, structure, pressure, behavior, impact, context).

2. Compute **relative volatility** and run filters:
   - `evaluate_spread_filter(relative_spread, spread_relative_threshold)`
   - `evaluate_volatility_filter(relative_volatility, volatility_relative_threshold)`
   - `evaluate_news_filter(universe, block_high_impact_news)`

3. Build **BUY** and **SELL** candidates:
   - `calculate_buy_candidate(analysis, market_bars, spread_filter, volatility_filter, instance_state)`
   - `calculate_sell_candidate(...)`
   - Candidate includes:
     - `valid`/`invalid_reason`
     - `entry_price`
     - `stop_loss`
     - `take_profit`
     - component scores, overall score.

4. Compute **scores**:
   - `calculate_buy_score`, `calculate_sell_score` using weights from config.
   - `ScoringResult` with `buy_score`, `sell_score`, `preferred_side`.

5. Resolve final **Decision**:
   - `evaluate_block_decision(block_reason)`:
     - If `block_reason` present (e.g. account not tradeable, invalid status), decision = `BLOCK`.
   - Else `evaluate_wait_decision(...)`:
     - Returns WAIT if:
       - both directions invalid, or
       - equal scores with no clear edge, or
       - execution not possible (e.g. risk rejects).
   - Else:
     - If `preferred_side == BUY` → `Decision.BUY`
     - If `preferred_side == SELL` → `Decision.SELL`

Result:
- `DecisionResult` with fields:
  - `decision`: `"BUY" | "SELL" | "WAIT" | "BLOCK"`
  - `reason`: full reason string (e.g. `"BUY: preferred side selected after scoring (...)"`
  - `preferred_side`
  - `buy_candidate`, `sell_candidate`
  - `analysis_context`

**Risk Engine (`run_risk_engine`)**:

Input:
- `decision_result: DecisionResult`
- `risk_config`
- `instance_state`
- `status` (from `status_{account}.json`)
- `trade_params` (e.g. `max_risk_per_trade`, `reward_ratio`, etc.)

Steps:
1. Check **hard constraints**:
   - Max open positions per instance.
   - Daily loss % vs `day_start_balance` and `peak_equity`.
   - Max drawdown % vs `day_start_balance`.
   - Max stop‑loss distance vs `max_stop_loss_pips`.

2. Compute **position size**:
   - Based on balance/equity, risk per trade %, SL distance, volume step.

3. Validate **SL/TP**:
   - `sl_tp.validate_sl_tp(...)` ensures:
     - SL/TP are at valid distances from entry.
     - Reward ratio meets configured `reward_ratio`.

Result:
- `RiskEngineResult`:
  - `result`: `"ALLOW" | "BLOCK"`
  - `position_size`
  - `reason`

**Risk result effect:**
- If **BLOCK**, even if decision is BUY/SELL, no OPEN is executed.  
  Risk effectively turns trade into non‑tradable; Decision may still say BUY/SELL, but execution is suppressed (`should_execute_trade` returns false).

---

### 1.4 Execution → control → MT4 → ack

**Execution engine:**
- `engine/execution/engine.py` (`run_execution_engine`)
- `engine/execution/command.py` (`OrderCommand`, `build_order_command`, `build_modify_order_command`, `build_close_order_command`, `build_management_order_command`)
- `engine/execution/control_writer.py` (`publish_control`)
- `engine/execution/ack_reader.py`
- Tests: `tests/execution/test_*.py`, `tests/integration/test_execution_pipeline.py`, `tests/e2e/test_full_cycle.py`, `tests/e2e/test_trade_management_cycle.py`

**Control path:**
1. **Resolve order command**:
   - `resolve_order_command(decision_result, risk_engine_result, management_result, ticket, side)`
   - Produces `OrderCommand`:
     - `action`: `OPEN` / `MODIFY` / `CLOSE` / `NONE`
     - `reason`: e.g. `"BUY: ..."` or `"TRADE_MANAGEMENT_PARTIAL_CLOSE: ..."` or `"TIME_STOP: ..."`
     - `side`, `volume`, `stop_loss`, `take_profit`.

2. **Retry safety**:
   - If `instance_state.last_command_id` is non‑empty, `validate_control_command_retry` ensures **new** command_id:
     - Same `command_id` twice → raises `ExecutionError` (no resend of identical control).

3. **Recovery‑aware control republish**:
   - `detect_unconfirmed_control` + `is_control_republish_allowed` guard re‑publishing when previous command has unresolved ACK.
   - If not allowed, returns `ExecutionResult` with `control_published=False` (no write).

4. **Publish control**:
   - `publish_control(paths, instance, order_command, timestamp_utc, retry_policy, retry_alert_context)` writes `control_{symbol}_{magic}.json` atomically with:
     - `schema_version`
     - `timestamp_utc`
     - `account_id`, `symbol`, `magic`
     - `action` (OPEN/MODIFY/CLOSE)
     - `reason`, `decision_id`, `side`, `volume`, SL/TP.

5. **MT4 EA** reads control and calls **OrderSend** / **OrderModify** / **OrderClose**; writes `ack_{symbol}_{magic}.json` with:
   - `status`: `SUCCESS` / `FAILED` / `REJECTED`
   - `ticket` (for OPEN)
   - `error_code`, `error_message` if failure.

6. **ACK reader**:
   - `read_ack_for_command(...)` ensures:
     - correct command_id
     - valid payload (via `AckRecord` model)
   - `interpret_ack(ack_record)` returns `AckInterpretation` with flags:
     - `is_success`, `is_failed`, `is_rejected`, `is_timeout`.

7. **State + journal update**:
   - `apply_ack_to_instance_state` updates `InstanceState`:
     - On OPEN SUCCESS: set `open_ticket`, `position_side`, `position_volume`, `position_entry_price`, SL/TP, `position_bars_open=1`.
     - On MODIFY SUCCESS: update SL/TP levels.
     - On CLOSE SUCCESS:
       - If partial volume: `reduce_position_volume` and set `partial_close_applied=True`.
       - Else: `clear_position` (no open position).
   - `log_trade_ack` / `log_trade_ack_timeout` write trade journal lines with event and status.
   - `archive_processed_control` + `archive_processed_ack` move the files to history.

8. **Timeout case**:
   - `wait_for_ack` uses `ack_timeout_ms` from config.
   - On timeout:
     - Logs timeout metric via `log_ack_timeout`.
     - Updates `InstanceState.last_ack_status = TIMEOUT`.
     - Archives control & ack (even if ack missing or inconsistent).
     - Writes trade journal timeout via `log_trade_ack_timeout`.

---

## 2. When BUY is opened

System issues an **OPEN BUY** when all of the following hold in one cycle:

1. **Valid data & status:**
   - Market, sensor, status, universe pass validators (no `ValidationResult` errors).
   - Status:
     - `connected == True`
     - `trade_allowed == True`

2. **Decision side = BUY:**
   - `run_decision_engine` decides `Decision.BUY`:
     - BUY candidate is `valid`.
     - Scoring prefers BUY over SELL:
       - `preferred_side == Side.BUY.value`
       - Not blocked by WAIT logic (no tie, no invalid both sides).

3. **Risk = ALLOW:**
   - `run_risk_engine` returns:
     - `result == RiskResult.ALLOW.value`
     - `position_size > 0`
     - SL/TP validated.

4. **Should execute trade:**
   - `should_execute_trade(...)` from `engine/core/cycle.py` returns `True`:
     - `decision_result.decision in {BUY, SELL}`
     - `risk_engine_result.result == ALLOW`
     - `runtime.allow_control_writes == True`

5. **No recovery blocks:**
   - Either no `unconfirmed` control or `is_control_republish_allowed(...)` approves a new command.

6. **Order command builds OPEN:**
   - `resolve_order_command(...)` builds `OrderCommand` with:
     - `action == OPEN`
     - `side == BUY`
     - `volume == position_size`
     - SL/TP from trade management/risk.

7. **MT4 ACK SUCCESS:**
   - EA executes order successfully, writes ACK with:
     - `status == SUCCESS`
     - `ticket` > 0.
   - `apply_ack_to_instance_state` sets `open_ticket`, `position_side=BUY`, `position_volume=volume`.

---

## 3. When SELL is opened

Exactly symmetric to BUY, with side = SELL:

Conditions:
1. Market/sensor/status/universe valid and trade_allowed.
2. Decision chooses `Decision.SELL` (SELL candidate valid, scoring prefers SELL).
3. Risk ALLOW with positive `position_size`.
4. `should_execute_trade` returns True.
5. Recovery allows publishing.
6. `OrderCommand.action == OPEN`, `side == SELL`.
7. ACK SUCCESS; state updated with SELL position.

---

## 4. When WAIT

WAIT is chosen when the system decides **not to open or close** any trade in that cycle due to trade logic, not hard errors.

Key conditions from `decision/wait_block.py` and tests:

1. **No clear preferred side:**
   - Both BUY and SELL candidates invalid, or
   - Both valid but:
     - Scores equal within tolerance (e.g. `EQUAL_SCORES` reason).

2. **Execution not appropriate:**
   - Spread filter or volatility filter fails (e.g. spread too wide), making execution unattractive.
   - News filter indicates no trading due to high impact context.

3. **Risk may block but decision still considered WAIT:**
   - Risk engine might block ALLOW/BLOCK at risk layer, but WAIT is still considered a decision when there is no actionable trade.

Result:
- `DecisionResult.decision == WAIT`
- `DecisionResult.reason` contains WAIT reason (e.g. `BOTH_DIRECTIONS_INVALID`, `EQUAL_SCORES`).
- No `OPEN` or management `MODIFY/CLOSE` command is produced.

---

## 5. When BLOCK

BLOCK is a **hard “do not trade”** decision for that cycle, caused by invalid preconditions or account constraints.

Sources (non‑exhaustive, see `engine/core/cycle.py`, `decision/wait_block.py`, `core/monitoring.py`):

1. **Status / account not tradeable:**
   - `status.trade_allowed == False` or not connected:
     - `build_account_block_reason` returns reason like `REASON_ACCOUNT_NOT_TRADEABLE`.
     - Decision engine returns `Decision.BLOCK` with that reason.

2. **Validator hard errors:**
   - Market or sensor validation fails (missing data, corrupted CSV, invalid timestamps):
     - Cycle logs validation error and ends; decision may be treated as BLOCK for monitoring.

3. **Risk rules:**
   - `run_risk_engine` might effectively block trades when:
     - Max open positions per instance reached.
     - Daily loss or drawdown exceeds limit.
     - SL/TP invalid with respect to risk parameters.
   - Decision may still be BUY/SELL, but no execution will occur; monitoring treats this as risk block.

4. **MT4 / control recovery:**
   - Recovery logic can block new control if previous command is unconfirmed and conditions forbid republish.

Result:
- Either explicit `Decision.BLOCK` with reason, or **no control publication** and monitoring health `"BLOCKED"`/`"ERROR"`.

---

## 6. When a trade is closed (full CLOSE)

Trade is fully closed when an effective **CLOSE** action drains the position volume to zero.

Paths:

1. **Manual risk/management close:**
   - Trade management (`risk/trade_management.py`) may decide CLOSE:
     - Time stop (bars_open ≥ `time_stop_max_bars`) → CLOSE full volume.
   - `resolve_order_command` builds `OrderCommand.action == CLOSE` with `volume == current_volume`.
   - ACK SUCCESS → `InstanceState.clear_position()`.

2. **External close (TP/SL on MT4):**
   - EA closes position due to TP/SL or manual user action.
   - Status `open_positions` no longer contains position for this instance.
   - `core/position_sync.reconcile_position_with_status(...)`:
     - Detects missing open position vs `InstanceState`.
     - Calls `log_external_position_close(...)`.
     - Clears position in `InstanceState` (`clear_position()`).

Result:
- `open_ticket == None`
- `position_volume == None`
- `position_side == None`
- Trade journal logs CLOSE (or external close) event.

---

## 7. When SL/TP are changed (MODIFY)

SL/TP are modified via **Trade Management** rules:

**Module:** `engine/risk/trade_management.py`  
**Tests:** `tests/risk/test_trade_management.py`, `tests/core/test_cycle.py::test_run_instance_trade_management_phase_returns_modify_for_breakeven_progress`

Rules:

1. **Breakeven (evaluate_breakeven):**
   - Condition:
     - Progress to TP ≥ `breakeven_progress_ratio` from config.
     - For BUY: price sufficiently beyond entry; for SELL: symmetrical.
   - Action:
     - New SL moved to entry price.
     - `TradeManagementResult.action == MODIFY`, reason starts with `"TRADE_MANAGEMENT_BREAKEVEN"`.

2. **Trailing stop (evaluate_trailing_stop):**
   - Condition:
     - Structure analysis provides `swing_low`, `swing_high`.
     - For BUY:
       - Candidate SL = `swing_low - trailing_buffer` > current SL and < current price.
     - For SELL:
       - Candidate SL = `swing_high + trailing_buffer` < current SL and > current price.
   - Action:
     - `MODIFY` with updated SL, same TP.

3. **Time stop (evaluate_time_stop):**
   - When `position_bars_open ≥ time_stop_max_bars`.
   - Action:
     - `CLOSE` full volume (see section 6).

4. **Priorities (`evaluate_trade_management`):**
   - Order:
     1. Time stop (CLOSE)
     2. Partial close
     3. Trailing stop (MODIFY)
     4. Breakeven (MODIFY)
   - First non‑None result wins.

Execution:
- If `TradeManagementResult.action == MODIFY`:
  - `resolve_order_command` builds MODIFY command with new SL/TP.
  - On ACK SUCCESS:
    - `InstanceState.update_position_levels(stop_loss, take_profit)` applies new levels.

---

## 8. When partial close happens

**Module:** `engine/risk/trade_management.py::evaluate_partial_close`  
**Tests:**
- `tests/risk/test_trade_management.py::test_evaluate_partial_close_generates_close_with_partial_volume`
- `tests/e2e/test_trade_management_cycle.py::test_e2e_open_partial_close_cycle_reduces_volume`
- `tests/core/test_position_sync.py::test_reconcile_position_with_status_logs_partial_close`

Conditions for **partial close**:

1. `partial_close_applied == False` in `InstanceState`.
2. `partial_close_progress_ratio > 0` and `partial_close_volume_ratio > 0`.
3. `volume_step > 0` (config).
4. Progress to TP ≥ `partial_close_progress_ratio`:
   - `compute_progress_to_take_profit` uses entry, TP, current price.
5. Computed `close_volume = volume * partial_close_volume_ratio` after step normalization:
   - `0 < close_volume < current_position_volume`.

Result:
- `TradeManagementResult` with:
  - `action == CLOSE`
  - `volume == close_volume`
  - `reason` contains `"TRADE_MANAGEMENT_PARTIAL_CLOSE: partial volume close triggered"`.

Execution:
- Execution engine sends CLOSE with partial volume.
- ACK SUCCESS:
  - `InstanceState.reduce_position_volume(volume=close_volume)` reduces volume and sets `partial_close_applied=True`.
  - Position remains open with reduced volume.

External partial closes (from MT4/manual):
- If EA/user closes part of position outside Python:
  - Status `open_positions` shows remaining volume smaller than `InstanceState.position_volume`.
  - `reconcile_position_with_status` detects mismatch:
    - Sets `external_partial_close=True`.
    - Calls `log_external_partial_position_close(...)`.
    - Updates `InstanceState` to new volume and marks external partial close in journal.

---

## 9. All risk blocks

Risk can block trade in several ways:

1. **Position limits:**
   - `max_open_positions_per_instance` in `config["risk"]`.
   - If exceeded, `RiskEngineResult.result == BLOCK`.

2. **Daily loss and drawdown:**
   - Based on `day_start_balance` and `peak_equity` in `InstanceState`.
   - If loss > `max_daily_loss_percent` or drawdown > `max_drawdown_percent`, risk returns BLOCK.

3. **Stop‑loss / TP validity (sl_tp):**
   - SL and TP must:
     - Respect min distance vs entry,
     - Match reward ratio constraints,
     - Not exceed `max_stop_loss_pips`.
   - Violations cause BLOCK.

4. **Volume constraints:**
   - If computed volume ≤ 0 or > allowed via margin, risk blocks the trade.

5. **Trade Management rules:**
   - Time stop closes existing position rather than open new ones — not exactly BLOCK but prevents prolonged exposure.

6. **Account/trading status:**
   - If status is not tradeable (see section 10), no ALLOW, and decision ends up BLOCK.

7. **Control republish safety:**
   - Recovery check denies re‑publishing control with same `command_id` or unconfirmed prior control.

---

## 10. All data validation blocks

Data validation is performed by loaders + validators:

1. **Market CSV:**
   - Correct header line.
   - At least required number of rows.
   - Per‑row type checks for numbers/time.
   - If invalid: `ValidationResult` with errors; cycle logs error and aborts before analysis.

2. **Sensor CSV:**
   - Spread line structure; ensures non‑negative spread, properly formatted.
   - Enforces economic consistency: `spread == ask - bid` and `spread_points == spread / point` (`sensor_validator.py`).

3. **Status JSON:**
   - Field presence and types.
   - `connected` and `trade_allowed` must be booleans.

4. **Universe JSON:**
   - `validate_universe_json` ensures:
     - Only allowed fields.
     - No trade signal fields from `UNIVERSE_FORBIDDEN_FIELDS`.
   - `parse_universe` must succeed.

5. **Config shape:**
   - `core/config.py::parse_config_payload` and `load_system_config`:
| `ai` | `mode`, `fail_closed`, `reject_action`, `timeout_ms`, `retry_max`, `retry_delay_ms` |
     - Reject “hard symbol lists”, “hard spread caps”, “hard digits/point/pip” fields.

6. **Stale data:**
   - `compute_data_freshness_ms` + `is_data_stale` in `core/monitoring.py`.
   - Stale data can:
     - cause cycle to be skipped (validation failure), or
     - produce alerts + metrics with `data_stale=True`.

7. **Timeout / cycle duration:**
   - Mid‑cycle timeout guard can abort cycle if `cycle_max_duration_ms` is exceeded, recording timeout reason.

---

## 11. All MT4 execution blocks

Execution can be blocked or limited at MT4 side:

1. **EA not connected / not exporting:**
   - `validate_mt4_exports` in `tools/validate_live.py` checks:
     - Presence + freshness of market, sensor, status files.
   - Missing/stale exports lead to LIVE validation failure (CLI).

2. **Order failures:**
   - MT4 `OrderSend` / `OrderModify` / `OrderClose` failures:
     - ACK `status == FAILED`/`REJECTED` with `error_code`/`error_message`.
   - Python:
     - Logs error via `log_ack_failure` (execution error journal).
     - `apply_ack_to_instance_state` keeps `last_ack_status` but does **not** change position on failure.

3. **Timeouts:**
   - If ACK not delivered by `ack_timeout_ms`, Python treats as timeout:
     - Trade journal records timeout.
     - Control and ACK are archived.
     - System will later recover based on status/open_positions (recovery logic).

---

## 12. Config parameters affecting decisions

**Key config fields (`config/system.json`):**

- `system.timeframe` (must be `"M1"`)
- `paths.*` (clients, logs, cache, history, universe dirs)
- `runtime`:
  - `cycle_interval_ms`
  - `ack_timeout_ms`
  - `retry_max`, `retry_delay_ms`
  - `data_stale_threshold_ms`
  - `cycle_max_duration_ms`
  - `metrics_interval_ms`
  - `auto_discover_instances`

- `instances[]`:
  - `account_id`, `symbol`, `magic`, `enabled`

- `risk`:
  - `max_open_positions_per_instance`
  - `max_daily_loss_percent`
  - `max_drawdown_percent`
  - `reward_ratio`
  - `max_risk_per_trade_percent`
  - `max_stop_loss_pips`
  - `volume_step`

- `analysis`:
  - `lookback_bars`
  - `spread_relative_threshold`
  - `volatility_relative_threshold`
  - `block_high_impact_news`
  - `stop_loss_buffer`
  - `weights` (momentum/trend/structure/pressure/behavior/impact/context)

- `journal.retention_days`
- `trade_management`:
  - `enabled`
  - `breakeven_progress_ratio`
  - `partial_close_progress_ratio`
  - `partial_close_volume_ratio`
  - `time_stop_max_bars`

- `dashboard.refresh_interval_ms`
- `logging.level`, `logging.format`

These parameters jointly define:
- Which instances exist and are allowed to trade.
- How analysis scores are computed and weighed.
- When spread/volatility/news filters block trades.
- When risk blocks trades or caps volume.
- When trade management modifies stops, closes trades, or partially closes.
- How fast the system cycles and when it declares timeouts or stale data.

---

## 13. 20 practical examples (input → expected decision)

The following are **conceptual** examples summarizing behavior implied by the code and test suite. Remember that exact numeric thresholds depend on config values.

1. **Clean BUY signal**
   - Market: trending up; analysis BUY score ≫ SELL; spread & volatility within thresholds; no high impact news.
   - Status: connected, trade_allowed=True.
   - Risk: within daily loss and drawdown limits.
   - Expected: `Decision.BUY`, `Risk.ALLOW`, execution sends `OPEN BUY`.

2. **Clean SELL signal**
   - Mirror of above in bearish regime.
   - Expected: `Decision.SELL`, `Risk.ALLOW`, `OPEN SELL`.

3. **Both directions invalid**
   - Analysis finds no valid BUY or SELL candidate (filters or score thresholds fail).
   - Expected: `Decision.WAIT` with reason `BOTH_DIRECTIONS_INVALID`.

4. **Equal scores**
   - BUY and SELL scores equal within tolerance, both valid.
   - Expected: `Decision.WAIT` with reason containing `EQUAL_SCORES`.

5. **Account not tradeable**
   - Status: `connected=False` or `trade_allowed=False`.
   - Expected: `Decision.BLOCK` with reason `ACCOUNT_NOT_TRADEABLE`; no control/ack.

6. **Spread too wide**
   - `relative_spread > spread_relative_threshold`.
   - Expected: filters mark spread unacceptable; decision likely WAIT/BLOCK (depending on other conditions).

7. **High volatility filter block**
   - `relative_volatility > volatility_relative_threshold`.
   - Expected: WAIT/BLOCK; no OPEN command.

8. **High impact news blocked**
   - Universe indicates high‑impact news and `block_high_impact_news=True`.
   - Expected: WAIT/BLOCK decision, no new trades.

9. **Risk limit exceeded (daily loss)**
   - `day_start_balance=10_000`, `peak_equity=10_500`, current equity=9_500.
   - If drawdown/loss > configured thresholds, `RiskEngineResult.BLOCK`.
   - Expected: decision may say BUY/SELL, but no OPEN executed.

10. **Max open positions reached**
    - Instance already has open position and `max_open_positions_per_instance=1`.
    - New BUY/SELL candidate arises.
    - Expected: Risk blocks; no new OPEN; instance continues managing existing position only.

11. **Breakeven SL move**
    - Position in profit such that progress ≥ `breakeven_progress_ratio` (e.g. 0.5).
    - Expected: `MODIFY` command setting SL to entry; `position_stop_loss` updated.

12. **Trailing stop move**
    - Structure analysis shows new swing high/low; trailing conditions satisfied.
    - Expected: `MODIFY` command with more favorable SL (closer to price but still safe).

13. **Time stop close**
    - `position_bars_open >= time_stop_max_bars` (e.g. 120 bars).
    - Expected: `CLOSE` full volume; `position_volume=None` afterwards.

14. **Partial close triggered**
    - Progress to TP ≥ `partial_close_progress_ratio` (e.g. 0.75); partial close not yet applied.
    - Expected: `CLOSE` with half volume (normalized to step); `partial_close_applied=True`; reduced volume remains.

15. **External full close via TP**
    - EA closes position at TP; Python not issuing CLOSE.
    - Status `open_positions` remove that ticket.
    - Next cycle:
      - `reconcile_position_with_status` detects missing open ticket vs `InstanceState`.
      - Expected: state cleared; external close logged.

16. **External partial close**
    - Volume reduced on MT4 side without Python CLOSE (manual partial close).
    - Status volume smaller than `InstanceState.position_volume`.
    - Expected: `reconcile_position_with_status` logs external partial close; updates volume and flags event in journal.

17. **ACK timeout**
    - Control published but no ack within `ack_timeout_ms`.
    - Expected:
      - `last_ack_status = TIMEOUT`.
      - Trade journal timeout entry.
      - Control/ack archived.
      - Recovery may later reconcile based on status/open_positions.

18. **Malformed market CSV**
    - Bad header / missing columns / not enough rows.
    - `validate_market_for_cycle` returns INVALID.
    - Expected: error logged, cycle aborted (no decision, no orders).

19. **Universe with trade signals (forbidden fields)**
    - Universe JSON contains `signal` or forbidden field from `UNIVERSE_FORBIDDEN_FIELDS`.
    - `validate_universe_json` or `parse_universe` fails.
    - Expected: LIVE validation detects error; depending on runtime path, cycle logs validation error and does not use such universe.

20. **Config with hard symbol list or spread cap**
    - `system.json` contains fields like `"symbols": [...]` or `"max_spread": ...`.
    - `parse_config_payload` rejects with `ConfigurationError`.
    - Expected: startup fails with configuration validation error.

---

## 14. References to key files, functions, tests

- **Loader / validator / normalizer:**
  - `engine/loader/*.py`
  - `engine/validator/*.py`
  - `engine/normalizer/*.py`
  - Tests: `tests/loader/`, `tests/normalizer/`

- **Analysis / Decision:**
  - `engine/analysis/*.py`
  - `engine/decision/*.py`
  - Tests: `tests/analysis/`, `tests/decision/`

- **Risk / Trade Management:**
  - `engine/risk/engine.py`
  - `engine/risk/rules.py`
  - `engine/risk/trade_management.py`
  - Tests: `tests/risk/test_engine.py`, `tests/risk/test_trade_management.py`

- **Execution / Recovery / History:**
  - `engine/execution/engine.py`
  - `engine/core/recovery.py`
  - `engine/core/history.py`
  - Tests: `tests/execution/`, `tests/core/test_recovery.py`, `tests/core/test_history*.py`, `tests/integration/test_execution_pipeline.py`, `tests/e2e/test_full_cycle.py`

- **Monitoring / Performance:**
  - `engine/core/monitoring.py`
  - `engine/core/performance.py`
  - Tests: `tests/core/test_monitoring.py`, `tests/core/test_performance.py`, `tests/performance/test_memory.py`

- **MQL4 integration:**
  - `mql4/Experts/SYSTEM_EA.mq4`
  - `mql4/Include/SYSTEM_*.mqh`
  - Tests: `tests/mql4/test_system_*.py`

- **Config:**
  - `SYSTEM/config/system.json`
  - `engine/core/config.py`
  - Tests: `tests/core/test_config.py`, `tests/tools/test_validate_live.py`

---

## 15. Unknowns without LIVE MT4 tests

Even with full static analysis and local tests, some aspects cannot be 100% confirmed without a real MT4 LIVE environment:

1. **Real MT4 order execution semantics:**
   - Exact mapping of Python control fields to MT4 `OrderSend` behavior under all broker conditions.

2. **Latency and race conditions:**
   - Real‑world timing between control write and ack write; potential re‑ordering and races on a real terminal under load.

3. **Broker‑specific errors:**
   - Error codes, slippage, partial fills, requotes, trade context busy conditions.

4. **Long‑term performance and memory behavior:**
   - Multi‑day runtime behavior, memory fragmentation, disk I/O performance in production.

5. **Multi‑account, multi‑symbol concurrency on real MT4 terminals:**
   - Behavior when multiple EAs and manual interventions occur simultaneously on the same account.

6. **File system behavior on non‑NTFS / networked disks:**
   - Atomic write assumptions on exotic or remote filesystems.

7. **Operational procedures:**
   - How operators manage restarts, config updates, and manual overrides in production.

For these areas, [`tools/validate_live.py`] and the E2E tests provide strong guidance, but a final “production‑ready” verdict requires at least one controlled LIVE MT4 validation run.

