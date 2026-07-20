from __future__ import annotations
from dataclasses import dataclass
from typing import Any, MutableMapping
import time
from engine.analysis.structure import StructureAnalysis, analyze_structure, analyze_structure_window
from engine.core.clock import format_utc_timestamp, now_utc
from engine.core.instance import Instance
from engine.core.lifecycle import LiveRuntime
from engine.core.paths import SystemPaths
from engine.core.performance import CycleTimingSnapshot, monotonic_elapsed_ms
from engine.core.position_sync import find_status_position, find_status_positions, reconcile_position_with_status
from engine.core.retry import RetryAlertContext, RetryPolicy, build_retry_policy
from engine.ai_decision_layer import AIDecisionMeta, AIQueryResult, apply_ai_to_decision_result, apply_risk_block_to_decision_result, get_ai_decision
from engine.risk.precheck import should_call_ai_layer
from engine.decision.engine import DecisionResult, run_decision_engine
from engine.execution.engine import ExecutionResult, is_valid_open_fill_ack, run_execution_engine
from engine.journal.decision_journal import log_decision
from engine.journal.error_journal import log_error
from engine.loader.market_loader import RawMarketData, load_market_data
from engine.loader.sensor_loader import RawSensorData, load_sensor_data
from engine.loader.status_loader import RawStatusData, load_status_data
from engine.loader.universe_loader import RawUniverseData, load_universe_data
from engine.normalizer.instrument_params import derive_instrument_params, detect_params_change
from engine.normalizer.market_normalizer import NormalizedMarketBar, normalize_market_csv
from engine.normalizer.spread_model import SpreadModelSnapshot, update_spread_model_from_sensor
from engine.protocol.constants import Decision, ErrorType, OrderAction, PROTOCOL_SCHEMA_VERSION, REASON_ACCOUNT_NOT_TRADEABLE, REASON_AMBIGUOUS_PENDING_EXECUTION, REASON_CLOSE_PENDING_RECONCILIATION, REASON_CYCLE_TIMEOUT, REASON_DATA_INVALID, REASON_ENTRY_DEFERRED, REASON_EXECUTION_OUTCOME_UNRESOLVED, REASON_INSTANCE_CONFLICT, REASON_STALE_STATUS_TIMESTAMP, REASON_STALE_UNIVERSE_TIMESTAMP, RiskResult, Side
from engine.protocol.errors import DataIOError, SystemError
from engine.protocol.models import SensorReading, StatusRecord, TradeManagementSettings, UniverseRecord
from engine.protocol.parser import parse_sensor_csv, parse_universe
from engine.reason import build_reason
from engine.risk.engine import RiskEngineResult, RiskEngineTradeParams, run_risk_engine
from engine.risk.trade_management import OpenPosition, TradeManagementConfig, TradeManagementResult, evaluate_trade_management
from engine.risk.money_step_trailing import (
    MONEY_TRAILING_STATE_MISSING,
    MoneyStepTrailingState,
    compute_net_profit_money,
    merge_technical_and_money_step_trailing,
)
from engine.decision.filters.news_filter import NEWS_FILTER_INACTIVE_REASON, evaluate_news_filter
from engine.state.instance_state import InstanceState
from engine.state.memory import InstanceMemory
from engine.validator.market_validator import ValidationResult, validate_market_csv
from engine.validator.sensor_validator import validate_sensor_csv
from engine.validator.status_validator import StatusValidationResult, validate_status_json
from engine.validator.universe_validator import validate_universe_json
MODULE_NAME = 'core.cycle'

@dataclass(frozen=True)
class CycleTimeoutGuard:
    cycle_started: float
    limit_ms: int

    def elapsed_ms(self) -> int:
        return monotonic_elapsed_ms(self.cycle_started)

    def is_exceeded(self) -> bool:
        return self.elapsed_ms() > self.limit_ms

@dataclass(frozen=True)
class InstanceCycleData:
    market_raw: RawMarketData
    sensor_raw: RawSensorData
    status_raw: RawStatusData
    universe_raw: RawUniverseData

@dataclass(frozen=True)
class InstanceCycleResult:
    instance: Instance
    timestamp_utc: str
    completed: bool
    error_logged: bool
    decision_result: DecisionResult | None = None
    risk_engine_result: RiskEngineResult | None = None
    decision_journal_logged: bool = False
    execution_result: ExecutionResult | None = None
    trade_executed: bool = False
    trade_intended: bool = False
    control_published: bool = False
    ack_received: bool = False
    broker_execution_confirmed: bool = False
    execution_failed: bool = False
    execution_unknown: bool = False
    ack_latency_ms: int | None = None
    performance_timings: CycleTimingSnapshot | None = None
    market_data_utc: str | None = None
    skip_reason: str | None = None

def build_trade_management_config(trade_params: RiskEngineTradeParams, *, trailing_buffer: float, settings: TradeManagementSettings, pip: float) -> TradeManagementConfig:
    price_trail_distance = settings.trailing_step_pips * pip if pip > 0 and settings.trailing_step_pips > 0 else 0.0
    return TradeManagementConfig(breakeven_progress_ratio=settings.breakeven_progress_ratio, trailing_buffer=trailing_buffer, partial_close_progress_ratio=settings.partial_close_progress_ratio, partial_close_volume_ratio=settings.partial_close_volume_ratio, time_stop_max_bars=settings.time_stop_max_bars, volume_step=trade_params.volume_step, price_trail_distance=price_trail_distance)

def _synthetic_reference_take_profit(*, side: str, entry_price: float, stop_loss: float, reward_ratio: float) -> float:
    if reward_ratio <= 0:
        return 0.0
    if side == Side.BUY.value and entry_price > stop_loss:
        return entry_price + (entry_price - stop_loss) * reward_ratio
    if side == Side.SELL.value and stop_loss > entry_price:
        return entry_price - (stop_loss - entry_price) * reward_ratio
    return 0.0

def resolve_open_position_from_state(instance_state: InstanceState, *, reward_ratio: float | None=None) -> OpenPosition | None:
    if instance_state.open_ticket is None or instance_state.position_side is None or instance_state.position_volume is None or (instance_state.position_entry_price is None) or (instance_state.position_stop_loss is None):
        return None
    broker_take_profit = instance_state.position_take_profit or 0.0
    management_take_profit = broker_take_profit if broker_take_profit > 0 else instance_state.position_reference_take_profit or 0.0
    if management_take_profit <= 0 and reward_ratio is not None:
        management_take_profit = _synthetic_reference_take_profit(side=instance_state.position_side, entry_price=instance_state.position_entry_price, stop_loss=instance_state.position_stop_loss, reward_ratio=reward_ratio)
    return OpenPosition(ticket=instance_state.open_ticket, side=instance_state.position_side, entry_price=instance_state.position_entry_price, stop_loss=instance_state.position_stop_loss, take_profit=management_take_profit, volume=instance_state.position_volume, bars_open=instance_state.position_bars_open, partial_close_applied=instance_state.partial_close_applied)

def resolve_trade_management_price(*, position_side: str, sensor_reading: SensorReading | None, market_bars: tuple[NormalizedMarketBar, ...] | None=None) -> float | None:
    if sensor_reading is None:
        return None
    if position_side == Side.BUY.value:
        return sensor_reading.bid
    return sensor_reading.ask

def is_sensor_fresh(sensor_reading: SensorReading | None, now_utc: str, threshold_ms: int) -> bool:
    if sensor_reading is None:
        return False
    from engine.core.monitoring import compute_data_freshness_ms, is_data_stale
    freshness_ms = compute_data_freshness_ms(sensor_reading.time_utc, now_utc)
    return not is_data_stale(freshness_ms, threshold_ms)

def run_instance_trade_management_phase(*, instance_memory: InstanceMemory, market_bars: tuple[NormalizedMarketBar, ...], runtime: LiveRuntime, trade_params: RiskEngineTradeParams | None=None, ai_allow_close: bool=True, sensor_reading: SensorReading | None=None, market_bar_time_utc: str | None=None, current_utc: str | None=None, status: StatusRecord | None=None) -> TradeManagementResult:
    if not runtime.config.trade_management.enabled:
        return TradeManagementResult(action=OrderAction.NONE.value, reason='')
    resolved_trade_params = trade_params or build_risk_trade_params(runtime)
    if instance_memory.instance_state.open_ticket is not None and market_bar_time_utc:
        instance_memory.instance_state.sync_position_bars_for_market_bar(market_bar_time_utc)
    position = resolve_open_position_from_state(instance_memory.instance_state, reward_ratio=runtime.config.risk.reward_ratio)
    trailing_lookback = runtime.config.trade_management.trailing_lookback_bars
    structure = resolve_structure_levels(market_bars, structure_lookback_bars=trailing_lookback)
    digits = instance_memory.instance_state.instrument_digits
    if digits <= 0 and market_bars:
        digits = market_bars[-1].digits
    pip = instance_memory.instance_state.instrument_pip
    if pip <= 0 and market_bars:
        pip = market_bars[-1].point * 10.0
    point = instance_memory.instance_state.instrument_point
    if point <= 0 and market_bars:
        point = market_bars[-1].point
    resolved_now = current_utc or now_utc()
    threshold_ms = runtime.config.runtime.data_stale_threshold_ms
    price = resolve_trade_management_price(position_side=instance_memory.instance_state.position_side or Side.BUY.value, sensor_reading=sensor_reading, market_bars=market_bars)
    sensor_fresh = is_sensor_fresh(sensor_reading, resolved_now, threshold_ms)
    if price is None or not sensor_fresh:
        if sensor_reading is None:
            reason = 'trade_management_skipped: missing sensor price'
        elif price is None:
            reason = 'trade_management_skipped: missing management price'
        else:
            from engine.core.monitoring import compute_data_freshness_ms
            freshness_ms = compute_data_freshness_ms(sensor_reading.time_utc, resolved_now)
            reason = f'trade_management_skipped: stale sensor price freshness_ms={freshness_ms} threshold_ms={threshold_ms}'
        return TradeManagementResult(action=OrderAction.NONE.value, reason=reason)
    technical = evaluate_trade_management(position=position, current_price=price, swing_low=structure.swing_low, swing_high=structure.swing_high, config=build_trade_management_config(resolved_trade_params, trailing_buffer=runtime.config.analysis.stop_loss_buffer, settings=runtime.config.trade_management, pip=pip), digits=digits, allow_close=runtime.config.trade_management.allow_close and ai_allow_close, use_fixed_take_profit=runtime.config.trade_management.use_fixed_take_profit)
    money_params = runtime.config.trade_management.money_step_trailing.to_params()
    if position is None or not money_params.enabled:
        return technical
    if not money_params.is_runnable():
        # Enabled with invalid values: refuse money-step (no invented defaults); keep technical trailing.
        return technical
    state = instance_memory.instance_state
    status_position = None
    if status is not None and state.open_ticket is not None:
        status_position = find_status_position(status, instance_memory.instance, open_ticket=state.open_ticket)
    profit = float(status_position.profit) if status_position is not None and status_position.profit is not None else 0.0
    swap = float(status_position.swap) if status_position is not None and status_position.swap is not None else 0.0
    commission = float(status_position.commission) if status_position is not None and status_position.commission is not None else 0.0
    net_profit = compute_net_profit_money(profit=profit, swap=swap, commission=commission)
    open_price = position.entry_price
    current_sl = position.stop_loss
    volume = position.volume
    tick_value = status.tick_value if status is not None else None
    tick_size = status.tick_size if status is not None else None
    stop_level = status.stop_level if status is not None else None
    freeze_level = status.freeze_level if status is not None else None
    price_tolerance = max(point, 10 ** (-digits) if digits > 0 else 0.0, 1e-05)
    modify_tp = position.take_profit if runtime.config.trade_management.use_fixed_take_profit else 0.0
    money_state = MoneyStepTrailingState(
        peak_net_profit_money=state.peak_net_profit_money,
        money_trailing_step_index=state.money_trailing_step_index,
        locked_profit_money=state.locked_profit_money,
        last_money_trailing_sl=state.last_money_trailing_sl,
    )
    state_missing = bool(state.money_trailing_state_missing)
    if state_missing:
        log_error(
            runtime.paths,
            instance_memory.instance,
            module=MODULE_NAME,
            error_type=ErrorType.VALIDATION.value,
            message=MONEY_TRAILING_STATE_MISSING,
            context={'ticket': state.open_ticket, 'reason': MONEY_TRAILING_STATE_MISSING},
        )
    pending_modify_sl = None
    if state.pending_execution_command_id is not None and state.last_money_trailing_sl is not None:
        pending_modify_sl = state.last_money_trailing_sl
    merge = merge_technical_and_money_step_trailing(
        technical_result=technical,
        params=money_params,
        state=money_state,
        side=position.side,
        open_price=open_price,
        current_sl=current_sl,
        current_price=price,
        net_profit_money=net_profit,
        current_swap=swap,
        current_commission=commission,
        tick_value=tick_value,
        tick_size=tick_size,
        volume=volume,
        digits=digits,
        point=point,
        stop_level=stop_level,
        freeze_level=freeze_level,
        price_tolerance=price_tolerance,
        modify_take_profit=modify_tp,
        sensor_fresh=sensor_fresh,
        pending_modify_sl=pending_modify_sl,
        state_missing=state_missing,
    )
    state.apply_money_trailing_state(
        peak_net_profit_money=merge.state.peak_net_profit_money,
        money_trailing_step_index=merge.state.money_trailing_step_index,
        locked_profit_money=merge.state.locked_profit_money,
        last_money_trailing_sl=merge.state.last_money_trailing_sl,
        ticket=state.open_ticket,
    )
    if merge.skip_reason == 'money_step_trailing_blocked_invalid_tick':
        log_error(
            runtime.paths,
            instance_memory.instance,
            module=MODULE_NAME,
            error_type=ErrorType.VALIDATION.value,
            message='money step trailing blocked: invalid tick value/size or volume',
            context={'tick_value': tick_value, 'tick_size': tick_size, 'volume': volume, 'ticket': state.open_ticket},
        )
    return merge.management_result

def _build_ai_market_context(*, decision_result: DecisionResult, spread_snapshot: SpreadModelSnapshot, market_bars: tuple[NormalizedMarketBar, ...]) -> dict[str, object]:
    return {'relative_spread': spread_snapshot.relative_spread, 'last_close': market_bars[-1].close, 'last_time_utc': str(market_bars[-1].time_utc), 'system_reason': decision_result.reason, 'buy_score': decision_result.buy_score, 'sell_score': decision_result.sell_score}

def run_instance_ai_risk_pipeline(*, decision_result: DecisionResult, instance_memory: InstanceMemory, status: StatusRecord, market_bars: tuple[NormalizedMarketBar, ...], runtime: LiveRuntime, spread_snapshot: SpreadModelSnapshot, trade_params: RiskEngineTradeParams | None, status_stale: bool=False, universe_stale: bool=False) -> tuple[DecisionResult, RiskEngineResult, AIDecisionMeta, AIQueryResult]:
    pending_blocks = instance_memory.instance_state.pending_execution_command_id is not None
    call_ai = should_call_ai_layer(decision_result=decision_result, status=status, instance_state=instance_memory.instance_state, risk_config=runtime.config.risk)
    if status_stale or universe_stale or pending_blocks:
        call_ai = False
        skip_reason = 'skipped_stale_or_pending' if (status_stale or universe_stale or pending_blocks) else 'skipped_risk_precheck'
    else:
        skip_reason = None if call_ai else 'skipped_risk_precheck'
    if decision_result.decision not in {Decision.BUY.value, Decision.SELL.value}:
        call_ai = False
        skip_reason = 'skipped_non_entry'
    ai_query = get_ai_decision(system_signal=decision_result.decision, market_context=_build_ai_market_context(decision_result=decision_result, spread_snapshot=spread_snapshot, market_bars=market_bars), ai_config=runtime.config.ai, skip_reason=None if call_ai else skip_reason)
    decision_result, ai_meta = apply_ai_to_decision_result(decision_result=decision_result, ai_query=ai_query, ai_config=runtime.config.ai)
    risk_engine_result = run_instance_risk_phase(decision_result=decision_result, instance_memory=instance_memory, status=status, market_bars=market_bars, runtime=runtime, trade_params=trade_params)
    decision_result = apply_risk_block_to_decision_result(decision_result=decision_result, risk_engine_result=risk_engine_result)
    return (decision_result, risk_engine_result, ai_meta, ai_query)

def should_execute_management_action(order_action: str) -> bool:
    return order_action in {OrderAction.MODIFY.value, OrderAction.CLOSE.value}

def build_risk_trade_params(runtime: LiveRuntime) -> RiskEngineTradeParams:
    risk = runtime.config.risk
    return RiskEngineTradeParams(volume_step=risk.volume_step, max_stop_loss_pips=risk.max_stop_loss_pips)

def _noop_management_result() -> TradeManagementResult:
    return TradeManagementResult(action=OrderAction.NONE.value, reason='')

def _management_only_decision(decision_id: str='management') -> DecisionResult:
    from engine.analysis.context import AnalysisContext
    from engine.decision.buy import BuyCandidate
    from engine.decision.sell import SellCandidate
    empty_buy = BuyCandidate(valid=False, invalid_reason='management_pass', entry_price=0.0, stop_loss=0.0, take_profit=0.0, component_scores={}, buy_score=0.0)
    empty_sell = SellCandidate(valid=False, invalid_reason='management_pass', entry_price=0.0, stop_loss=0.0, take_profit=0.0, component_scores={}, sell_score=0.0)
    ctx = AnalysisContext(session='UNKNOWN', regime='ranging', news_active=False, context_quality=0.0, trade_environment='NEUTRAL')
    return DecisionResult(decision_id=decision_id, decision=Decision.WAIT.value, reason='management_pass', preferred_side='NONE', buy_candidate=empty_buy, sell_candidate=empty_sell, buy_score=0.0, sell_score=0.0, analysis_context=ctx)

def _blocked_risk(reason: str='') -> RiskEngineResult:
    return RiskEngineResult(result=RiskResult.BLOCK.value, reason=reason or 'management_pass', position_size=None, stop_loss=None, take_profit=None)

def resolve_use_global_universe(paths: SystemPaths) -> bool:
    return paths.universe_file.exists()

def load_instance_cycle_data(paths: SystemPaths, instance: Instance, *, use_global_universe: bool | None=None, cache: MutableMapping[str, Any] | None=None, retry_policy: RetryPolicy | None=None, retry_alert_context: RetryAlertContext | None=None) -> InstanceCycleData:
    from engine.core.mt4_bridge import mirror_common_bridge_to_deployment
    mirror_common_bridge_to_deployment(paths)
    resolved_use_global = resolve_use_global_universe(paths) if use_global_universe is None else use_global_universe
    return InstanceCycleData(market_raw=load_market_data(paths, instance, cache=cache, retry_policy=retry_policy, retry_alert_context=retry_alert_context), sensor_raw=load_sensor_data(paths, instance, cache=cache, retry_policy=retry_policy, retry_alert_context=retry_alert_context), status_raw=load_status_data(paths, instance.account_id, cache=cache, retry_policy=retry_policy, retry_alert_context=retry_alert_context), universe_raw=load_universe_data(paths, instance.account_id, use_global_universe=resolved_use_global, cache=cache, retry_policy=retry_policy, retry_alert_context=retry_alert_context))

def validate_market_for_cycle(market_raw: RawMarketData) -> tuple[NormalizedMarketBar, ...] | ValidationResult:
    from engine.core.atomic_io import atomic_write_text
    from engine.validator.market_validator import sanitize_market_csv
    sanitized = sanitize_market_csv(market_raw.raw_text)
    raw_text = sanitized.raw_text
    if sanitized.changed:
        try:
            atomic_write_text(market_raw.file_path, raw_text)
        except OSError:
            # Still attempt the cycle on the cleaned in-memory copy.
            pass
    validation = validate_market_csv(raw_text)
    if not validation.is_valid:
        return validation
    return normalize_market_csv(raw_text)

def validate_sensor_for_cycle(sensor_raw: RawSensorData) -> SensorReading | ValidationResult:
    from engine.core.atomic_io import atomic_write_text
    from engine.validator.sensor_validator import sanitize_sensor_csv
    sanitized = sanitize_sensor_csv(sensor_raw.raw_text)
    raw_text = sanitized.raw_text
    if sanitized.changed:
        try:
            atomic_write_text(sensor_raw.file_path, raw_text)
        except OSError:
            pass
    validation = validate_sensor_csv(raw_text)
    if not validation.is_valid:
        return validation
    readings = parse_sensor_csv(raw_text)
    if not readings:
        return ValidationResult(status=validation.status, errors=('sensor csv contains no readings',), row_count=0)
    return readings[-1]

def validate_status_for_cycle(status_raw: RawStatusData) -> StatusValidationResult:
    return validate_status_json(status_raw.raw_text)

def validate_universe_for_cycle(universe_raw: RawUniverseData) -> UniverseRecord | ValidationResult:
    validation = validate_universe_json(universe_raw.raw_text)
    if not validation.is_valid:
        return validation
    return parse_universe(universe_raw.raw_text)

def build_account_block_reason(status: StatusRecord) -> str | None:
    if status.connected and status.trade_allowed:
        return None
    return build_reason(REASON_ACCOUNT_NOT_TRADEABLE, 'account is not tradeable')

def build_invalid_status_block_reason(errors: tuple[str, ...] | list[str]) -> str:
    return build_reason(REASON_DATA_INVALID, 'status validation failed', errors=list(errors))

def build_placeholder_status_record(*, account_id: str, timestamp_utc: str) -> StatusRecord:
    return StatusRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc=timestamp_utc, account_id=account_id, connected=False, trade_allowed=False, balance=0.0, equity=0.0, margin_free=0.0, ea_version='unknown')

def update_instance_instrument_state(instance_memory: InstanceMemory, market_bars: tuple[NormalizedMarketBar, ...]) -> None:
    params = derive_instrument_params(market_bars)
    current_digits = instance_memory.instance_state.instrument_digits
    current_point = instance_memory.instance_state.instrument_point
    if current_digits > 0 and current_point > 0:
        from engine.normalizer.instrument_params import InstrumentParams
        if not detect_params_change(InstrumentParams(symbol=instance_memory.instance.symbol, digits=current_digits, point=current_point, pip=instance_memory.instance_state.instrument_pip), params):
            return
    instance_memory.instance_state.update_instrument(digits=params.digits, point=params.point, pip=params.pip)

def update_instance_spread_model(*, instance_memory: InstanceMemory, spread_models: dict[tuple[str, str, int], SpreadModelSnapshot], sensor_reading: SensorReading, lookback_bars: int, timestamp_utc: str) -> SpreadModelSnapshot:
    key = instance_memory.instance.instance_key
    existing = spread_models.get(key)
    history = existing.history if existing is not None else ()
    snapshot = update_spread_model_from_sensor(history, sensor_reading, lookback_bars=lookback_bars)
    spread_models[key] = snapshot
    instance_memory.spread_state.update_from_snapshot(snapshot, timestamp_utc)
    return snapshot

def resolve_structure_levels(market_bars: tuple[NormalizedMarketBar, ...], *, structure_lookback_bars: int) -> StructureAnalysis:
    return analyze_structure_window(market_bars, structure_lookback_bars=structure_lookback_bars)

def run_instance_decision_phase(*, universe: UniverseRecord, market_bars: tuple[NormalizedMarketBar, ...], instance_memory: InstanceMemory, relative_spread: float, runtime: LiveRuntime, block_reason: str | None=None, current_spread: float=0.0) -> DecisionResult:
    return run_decision_engine(universe=universe, market_bars=market_bars, instance_state=instance_memory.instance_state, relative_spread=relative_spread, system_config=runtime.config, block_reason=block_reason, paths=runtime.paths)

def run_instance_risk_phase(*, decision_result: DecisionResult, instance_memory: InstanceMemory, status: StatusRecord, market_bars: tuple[NormalizedMarketBar, ...], runtime: LiveRuntime, trade_params: RiskEngineTradeParams | None=None) -> RiskEngineResult:
    structure = resolve_structure_levels(market_bars, structure_lookback_bars=runtime.config.analysis.structure_lookback_bars)
    return run_risk_engine(decision_result=decision_result, risk_config=runtime.config.risk, instance_state=instance_memory.instance_state, status=status, trade_params=trade_params or build_risk_trade_params(runtime), swing_low=structure.swing_low, swing_high=structure.swing_high, use_fixed_take_profit=runtime.config.trade_management.use_fixed_take_profit)

def should_execute_trade(*, runtime: LiveRuntime, decision_result: DecisionResult, risk_engine_result: RiskEngineResult) -> bool:
    if not runtime.allow_control_writes:
        return False
    if decision_result.decision not in {Decision.BUY.value, Decision.SELL.value}:
        return False
    return risk_engine_result.result == RiskResult.ALLOW.value

def apply_closed_bar_entry_gate(*, runtime: LiveRuntime, instance_state: InstanceState, decision_result: DecisionResult, risk_engine_result: RiskEngineResult, market_bar_time_utc: str | None) -> RiskEngineResult:
    if not runtime.config.runtime.execute_entries_on_closed_bar_only:
        return risk_engine_result
    if not market_bar_time_utc:
        return risk_engine_result
    previous_bar = instance_state.last_seen_market_bar_utc
    instance_state.last_seen_market_bar_utc = market_bar_time_utc
    if not should_execute_trade(runtime=runtime, decision_result=decision_result, risk_engine_result=risk_engine_result):
        return risk_engine_result
    if previous_bar == market_bar_time_utc:
        return RiskEngineResult(result=RiskResult.BLOCK.value, reason=build_reason(REASON_ENTRY_DEFERRED, 'open entry deferred until next closed M1 bar', market_bar_time_utc=market_bar_time_utc), position_size=None, stop_loss=None, take_profit=None)
    return risk_engine_result

def _log_cycle_error(paths: SystemPaths, instance: Instance, *, message: str, context: dict[str, object] | None=None) -> None:
    log_error(paths, instance, module=MODULE_NAME, error_type=ErrorType.VALIDATION.value, message=message, context=context)

def _build_cycle_timings(*, cycle_started: float, load_duration_ms: int, analysis_duration_ms: int, decision_duration_ms: int) -> CycleTimingSnapshot:
    return CycleTimingSnapshot(cycle_duration_ms=monotonic_elapsed_ms(cycle_started), load_duration_ms=load_duration_ms, analysis_duration_ms=analysis_duration_ms, decision_duration_ms=decision_duration_ms, io_wait_ms=load_duration_ms)

def _log_stale_data_skip(paths: SystemPaths, instance: Instance, *, market_freshness_ms: int, sensor_freshness_ms: int, bar_freshness_ms: int, sensor_content_freshness_ms: int, threshold_ms: int, reason: str) -> None:
    log_error(paths, instance, module=MODULE_NAME, error_type=ErrorType.VALIDATION.value, message='cycle skipped due to stale market or sensor data', context={'reason': REASON_DATA_INVALID, 'detail': reason, 'market_file_freshness_ms': market_freshness_ms, 'sensor_file_freshness_ms': sensor_freshness_ms, 'bar_content_freshness_ms': bar_freshness_ms, 'sensor_content_freshness_ms': sensor_content_freshness_ms, 'threshold_ms': threshold_ms})

def _block_open_risk_result(reason: str) -> RiskEngineResult:
    return RiskEngineResult(result=RiskResult.BLOCK.value, reason=reason, position_size=None, stop_loss=None, take_profit=None)

def _abort_cycle_timeout(*, runtime: LiveRuntime, instance: Instance, timeout_guard: CycleTimeoutGuard, instance_memory: InstanceMemory | None=None) -> InstanceCycleResult:
    log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.PROTOCOL.value, message='cycle exceeded configured maximum duration', context={'reason': REASON_CYCLE_TIMEOUT, 'cycle_duration_ms': timeout_guard.elapsed_ms(), 'cycle_max_duration_ms': timeout_guard.limit_ms})
    if instance_memory is not None:
        instance_memory.instance_state.save(runtime.paths)
        if instance_memory.spread_state.record is not None:
            instance_memory.spread_state.save(runtime.paths)
    timings = CycleTimingSnapshot(cycle_duration_ms=timeout_guard.elapsed_ms(), load_duration_ms=timeout_guard.elapsed_ms(), analysis_duration_ms=0, decision_duration_ms=0, io_wait_ms=timeout_guard.elapsed_ms())
    return InstanceCycleResult(instance=instance, timestamp_utc=now_utc(), completed=False, error_logged=True, performance_timings=timings, skip_reason=REASON_CYCLE_TIMEOUT)

def _enforce_cycle_duration_limit(*, runtime: LiveRuntime, instance: Instance, cycle_duration_ms: int) -> bool:
    limit_ms = runtime.config.runtime.cycle_max_duration_ms
    if cycle_duration_ms <= limit_ms:
        return False
    log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.PROTOCOL.value, message='cycle exceeded configured maximum duration', context={'reason': REASON_CYCLE_TIMEOUT, 'cycle_duration_ms': cycle_duration_ms, 'cycle_max_duration_ms': limit_ms})
    return True

def _finalize_cycle_state(*, instance_memory: InstanceMemory, runtime: LiveRuntime, decision_result: DecisionResult, timestamp_utc: str) -> None:
    runtime.memory.update_analysis_decision(instance_memory.instance, analysis_context=decision_result.analysis_context, decision_result=decision_result)
    instance_memory.instance_state.update_cycle(decision=decision_result.decision, reason=decision_result.reason, cycle_utc=timestamp_utc)
    instance_memory.instance_state.save(runtime.paths)
    if instance_memory.spread_state.record is not None:
        instance_memory.spread_state.save(runtime.paths)

def run_instance_cycle(runtime: LiveRuntime, instance: Instance, *, use_global_universe: bool | None=None, trade_params: RiskEngineTradeParams | None=None, timestamp_utc: str | None=None, cache: MutableMapping[str, Any] | None=None) -> InstanceCycleResult:
    resolved_timestamp = timestamp_utc or now_utc()
    instance_memory = runtime.memory.get_or_create(instance)
    from engine.core.recovery import sync_instance_state
    sync_instance_state(runtime, instance)
    retry_policy = build_retry_policy(runtime.config.runtime)
    retry_alert_context = RetryAlertContext(logger=runtime.system_logger, instance=instance, operation='load instance cycle data')
    timeout_guard = CycleTimeoutGuard(cycle_started=time.monotonic(), limit_ms=runtime.config.runtime.cycle_max_duration_ms)
    cycle_started = timeout_guard.cycle_started
    load_started = time.monotonic()
    load_duration_ms = 0
    analysis_duration_ms = 0
    decision_duration_ms = 0

    def _cycle_result(**kwargs: object) -> InstanceCycleResult:
        timings = _build_cycle_timings(cycle_started=cycle_started, load_duration_ms=load_duration_ms or monotonic_elapsed_ms(load_started), analysis_duration_ms=analysis_duration_ms, decision_duration_ms=decision_duration_ms)
        return InstanceCycleResult(performance_timings=timings, **kwargs)
    try:
        loaded = load_instance_cycle_data(runtime.paths, instance, use_global_universe=use_global_universe, cache=cache, retry_policy=retry_policy, retry_alert_context=retry_alert_context)
    except DataIOError as exc:
        _log_cycle_error(runtime.paths, instance, message='failed to load instance cycle data', context={'error': str(exc)})
        return _cycle_result(instance=instance, timestamp_utc=resolved_timestamp, completed=False, error_logged=True, skip_reason=f'load_failed:{exc}')
    load_duration_ms = monotonic_elapsed_ms(load_started)
    if timeout_guard.is_exceeded():
        return _abort_cycle_timeout(runtime=runtime, instance=instance, timeout_guard=timeout_guard, instance_memory=instance_memory)
    market_result = validate_market_for_cycle(loaded.market_raw)
    if isinstance(market_result, ValidationResult):
        _log_cycle_error(runtime.paths, instance, message='market validation failed', context={'errors': list(market_result.errors)})
        return _cycle_result(instance=instance, timestamp_utc=resolved_timestamp, completed=False, error_logged=True, skip_reason=f'market_invalid:{";".join(market_result.errors[:2])}')
    market_bars = market_result
    runtime.memory.update_market_history(instance, market_bars)
    sensor_result = validate_sensor_for_cycle(loaded.sensor_raw)
    if isinstance(sensor_result, ValidationResult):
        _log_cycle_error(runtime.paths, instance, message='sensor validation failed', context={'errors': list(sensor_result.errors)})
        return _cycle_result(instance=instance, timestamp_utc=resolved_timestamp, completed=False, error_logged=True, skip_reason=f'sensor_invalid:{";".join(sensor_result.errors[:2])}')
    sensor_reading = sensor_result
    stale_threshold_ms = runtime.config.runtime.data_stale_threshold_ms
    from engine.core.monitoring import compute_data_freshness_ms, is_data_stale
    market_data_utc = format_utc_timestamp(market_bars[-1].time_utc)
    sensor_data_utc = sensor_reading.time_utc
    market_freshness_ms = compute_data_freshness_ms(loaded.market_raw.modified_utc, resolved_timestamp)
    sensor_freshness_ms = compute_data_freshness_ms(loaded.sensor_raw.modified_utc, resolved_timestamp)
    bar_freshness_ms = compute_data_freshness_ms(market_data_utc, resolved_timestamp)
    sensor_content_freshness_ms = compute_data_freshness_ms(sensor_data_utc, resolved_timestamp)
    market_file_stale = is_data_stale(market_freshness_ms, stale_threshold_ms)
    sensor_file_stale = is_data_stale(sensor_freshness_ms, stale_threshold_ms)
    bar_content_stale = is_data_stale(bar_freshness_ms, stale_threshold_ms)
    sensor_content_stale = is_data_stale(sensor_content_freshness_ms, stale_threshold_ms)
    # Full-cycle skip only when market file mtime is unusable; content staleness gates OPEN/trailing below.
    if market_file_stale and sensor_file_stale:
        stale_reason = f'stale_data:market_file={market_freshness_ms}ms sensor_file={sensor_freshness_ms}ms bar_content={bar_freshness_ms}ms sensor_content={sensor_content_freshness_ms}ms threshold={stale_threshold_ms}ms'
        _log_stale_data_skip(runtime.paths, instance, market_freshness_ms=market_freshness_ms, sensor_freshness_ms=sensor_freshness_ms, bar_freshness_ms=bar_freshness_ms, sensor_content_freshness_ms=sensor_content_freshness_ms, threshold_ms=stale_threshold_ms, reason=stale_reason)
        return _cycle_result(instance=instance, timestamp_utc=resolved_timestamp, completed=False, error_logged=True, market_data_utc=market_data_utc, skip_reason=stale_reason)
    if market_file_stale or bar_content_stale or sensor_file_stale or sensor_content_stale:
        log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.VALIDATION.value, message='stale data detected; applying precise open/trailing gates', context={'reason': REASON_DATA_INVALID, 'market_file_stale': market_file_stale, 'bar_content_stale': bar_content_stale, 'sensor_file_stale': sensor_file_stale, 'sensor_content_stale': sensor_content_stale, 'market_file_freshness_ms': market_freshness_ms, 'bar_content_freshness_ms': bar_freshness_ms, 'sensor_file_freshness_ms': sensor_freshness_ms, 'sensor_content_freshness_ms': sensor_content_freshness_ms, 'threshold_ms': stale_threshold_ms})
    stale_bar_blocks_open = market_file_stale or bar_content_stale
    stale_sensor_blocks_trailing = sensor_file_stale or sensor_content_stale
    universe_result = validate_universe_for_cycle(loaded.universe_raw)
    if isinstance(universe_result, ValidationResult):
        _log_cycle_error(runtime.paths, instance, message='universe validation failed', context={'errors': list(universe_result.errors)})
        return _cycle_result(instance=instance, timestamp_utc=resolved_timestamp, completed=False, error_logged=True, market_data_utc=market_data_utc, skip_reason=f'universe_invalid:{";".join(universe_result.errors[:2])}')
    universe = universe_result
    universe_content_freshness_ms = compute_data_freshness_ms(universe.timestamp_utc, resolved_timestamp)
    universe_stale = is_data_stale(universe_content_freshness_ms, stale_threshold_ms)
    if universe_stale:
        log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.VALIDATION.value, message='stale universe timestamp', context={'reason': REASON_STALE_UNIVERSE_TIMESTAMP, 'universe_content_freshness_ms': universe_content_freshness_ms, 'threshold_ms': stale_threshold_ms})
    status_result = validate_status_for_cycle(loaded.status_raw)
    if not status_result.is_valid or status_result.record is None:
        _log_cycle_error(runtime.paths, instance, message='status validation failed', context={'errors': list(status_result.errors)})
        block_reason = build_invalid_status_block_reason(status_result.errors)
        placeholder_status = build_placeholder_status_record(account_id=instance.account_id, timestamp_utc=resolved_timestamp)
        update_instance_instrument_state(instance_memory, market_bars)
        spread_snapshot = update_instance_spread_model(instance_memory=instance_memory, spread_models=runtime.spread_models, sensor_reading=sensor_reading, lookback_bars=runtime.config.analysis.lookback_bars, timestamp_utc=resolved_timestamp)
        decision_result = run_instance_decision_phase(universe=universe, market_bars=market_bars, instance_memory=instance_memory, relative_spread=spread_snapshot.relative_spread, runtime=runtime, block_reason=block_reason, current_spread=spread_snapshot.current_spread)
        decision_result, risk_engine_result, ai_meta, ai_query = run_instance_ai_risk_pipeline(decision_result=decision_result, instance_memory=instance_memory, status=placeholder_status, market_bars=market_bars, runtime=runtime, spread_snapshot=spread_snapshot, trade_params=trade_params, status_stale=True, universe_stale=universe_stale)
        effective_risk = apply_closed_bar_entry_gate(runtime=runtime, instance_state=instance_memory.instance_state, decision_result=decision_result, risk_engine_result=risk_engine_result, market_bar_time_utc=market_data_utc)
        log_decision(runtime.paths, instance, decision_result, effective_risk, timestamp_utc=resolved_timestamp, ai_meta=ai_meta)
        _finalize_cycle_state(instance_memory=instance_memory, runtime=runtime, decision_result=decision_result, timestamp_utc=resolved_timestamp)
        return _cycle_result(instance=instance, timestamp_utc=resolved_timestamp, completed=False, error_logged=True, decision_result=decision_result, risk_engine_result=risk_engine_result, decision_journal_logged=True, market_data_utc=market_data_utc, skip_reason=f'status_invalid:{";".join(status_result.errors[:2])}')
    status = status_result.record
    status_content_freshness_ms = compute_data_freshness_ms(status.timestamp_utc, resolved_timestamp)
    status_stale = is_data_stale(status_content_freshness_ms, stale_threshold_ms)
    if status_stale:
        log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.VALIDATION.value, message='stale status timestamp', context={'reason': REASON_STALE_STATUS_TIMESTAMP, 'status_content_freshness_ms': status_content_freshness_ms, 'threshold_ms': stale_threshold_ms})
    sync_result = None
    if not status_stale:
        sync_result = reconcile_position_with_status(runtime.paths, instance, instance_memory.instance_state, status, timestamp_utc=resolved_timestamp)
    if timeout_guard.is_exceeded():
        instance_memory.instance_state.save(runtime.paths)
        return _abort_cycle_timeout(runtime=runtime, instance=instance, timeout_guard=timeout_guard, instance_memory=instance_memory)
    update_instance_instrument_state(instance_memory, market_bars)
    spread_snapshot = update_instance_spread_model(instance_memory=instance_memory, spread_models=runtime.spread_models, sensor_reading=sensor_reading, lookback_bars=runtime.config.analysis.lookback_bars, timestamp_utc=resolved_timestamp)
    block_reason = build_account_block_reason(status)
    news_probe = evaluate_news_filter(universe, block_high_impact_news=runtime.config.analysis.block_high_impact_news)
    if news_probe.reason == NEWS_FILTER_INACTIVE_REASON:
        log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.VALIDATION.value, message='news filter inactive', context={'reason': NEWS_FILTER_INACTIVE_REASON, 'block_high_impact_news': runtime.config.analysis.block_high_impact_news})
    resolved_trade_params = trade_params or build_risk_trade_params(runtime)
    execution_result: ExecutionResult | None = None
    trade_intended = False
    control_published = False
    ack_received = False
    broker_execution_confirmed = bool(sync_result.broker_execution_confirmed) if sync_result is not None else False
    execution_failed = False
    execution_unknown = False
    trade_executed = False
    ack_latency_ms: int | None = None
    # Trade management FIRST (before entry/AI), when status+sensor are fresh and a position is open.
    # Skip TM while close_pending_reconciliation — ticket is missing from status until history confirms.
    management_result = _noop_management_result()
    management_executed_close = False
    management_blocked = status_stale or stale_sensor_blocks_trailing or instance_memory.instance_state.close_pending_reconciliation
    if not management_blocked and instance_memory.instance_state.open_ticket is not None:
        management_result = run_instance_trade_management_phase(instance_memory=instance_memory, market_bars=market_bars, runtime=runtime, trade_params=resolved_trade_params, ai_allow_close=True, sensor_reading=sensor_reading, market_bar_time_utc=market_data_utc, current_utc=resolved_timestamp, status=status)
    if runtime.allow_control_writes and should_execute_management_action(management_result.action) and not status_stale:
        if timeout_guard.is_exceeded():
            instance_memory.instance_state.save(runtime.paths)
            return _abort_cycle_timeout(runtime=runtime, instance=instance, timeout_guard=timeout_guard, instance_memory=instance_memory)
        trade_intended = True
        execution_started = time.monotonic()
        management_execution = run_execution_engine(paths=runtime.paths, instance=instance, instance_state=instance_memory.instance_state, decision_result=_management_only_decision(), risk_engine_result=_blocked_risk(), runtime=runtime.config.runtime, management_result=management_result, timestamp_utc=resolved_timestamp, retry_alert_context=RetryAlertContext(logger=runtime.system_logger, instance=instance, operation='management execution io'), position_last_bar_utc=market_data_utc)
        ack_latency_ms = int((time.monotonic() - execution_started) * 1000)
        execution_result = management_execution
        control_published = bool(management_execution.control_published)
        ack = management_execution.ack_interpretation
        if ack is not None:
            if ack.is_timeout:
                execution_unknown = True
            else:
                ack_received = True
                if ack.is_success:
                    broker_execution_confirmed = True
                if ack.is_failed or ack.is_rejected:
                    execution_failed = True
        trade_executed = broker_execution_confirmed
        if management_result.action == OrderAction.CLOSE.value:
            management_executed_close = True
    # Entry decision analysis AFTER trade management / MODIFY ACK.
    analysis_started = time.monotonic()
    ai_query: AIQueryResult | None = None
    try:
        decision_result = run_instance_decision_phase(universe=universe, market_bars=market_bars, instance_memory=instance_memory, relative_spread=spread_snapshot.relative_spread, runtime=runtime, block_reason=block_reason, current_spread=spread_snapshot.current_spread)
        decision_result, risk_engine_result, ai_meta, ai_query = run_instance_ai_risk_pipeline(decision_result=decision_result, instance_memory=instance_memory, status=status, market_bars=market_bars, runtime=runtime, spread_snapshot=spread_snapshot, trade_params=trade_params, status_stale=status_stale, universe_stale=universe_stale)
        analysis_duration_ms = monotonic_elapsed_ms(analysis_started)
        decision_duration_ms = analysis_duration_ms
    except SystemError as exc:
        analysis_duration_ms = monotonic_elapsed_ms(analysis_started)
        return _cycle_result(instance=instance, timestamp_utc=resolved_timestamp, completed=False, error_logged=True, skip_reason=f'decision_error:{exc}')
    effective_risk = apply_closed_bar_entry_gate(runtime=runtime, instance_state=instance_memory.instance_state, decision_result=decision_result, risk_engine_result=risk_engine_result, market_bar_time_utc=market_data_utc)
    if should_execute_trade(runtime=runtime, decision_result=decision_result, risk_engine_result=effective_risk):
        if instance_memory.instance_state.pending_execution_command_id is not None:
            effective_risk = _block_open_risk_result(build_reason(REASON_EXECUTION_OUTCOME_UNRESOLVED, 'pending execution outcome blocks new OPEN', pending_command_id=instance_memory.instance_state.pending_execution_command_id))
            log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.EXECUTION.value, message='new OPEN blocked due to unresolved pending execution', context={'reason': REASON_EXECUTION_OUTCOME_UNRESOLVED, 'pending_command_id': instance_memory.instance_state.pending_execution_command_id})
        elif instance_memory.instance_state.ambiguous_pending_execution:
            effective_risk = _block_open_risk_result(build_reason(REASON_AMBIGUOUS_PENDING_EXECUTION, 'ambiguous pending OPEN blocks new OPEN'))
            log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.EXECUTION.value, message='new OPEN blocked due to ambiguous pending execution', context={'reason': REASON_AMBIGUOUS_PENDING_EXECUTION})
        elif instance_memory.instance_state.close_pending_reconciliation:
            effective_risk = _block_open_risk_result(build_reason(REASON_CLOSE_PENDING_RECONCILIATION, 'close pending reconciliation blocks new OPEN', ticket=instance_memory.instance_state.close_pending_ticket))
            log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.PROTOCOL.value, message='new OPEN blocked due to close pending reconciliation', context={'reason': REASON_CLOSE_PENDING_RECONCILIATION, 'ticket': instance_memory.instance_state.close_pending_ticket})
        elif status_stale:
            effective_risk = _block_open_risk_result(build_reason(REASON_STALE_STATUS_TIMESTAMP, 'stale status blocks new OPEN', status_content_freshness_ms=status_content_freshness_ms, threshold_ms=stale_threshold_ms))
            log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.VALIDATION.value, message='new OPEN blocked due to stale status', context={'reason': REASON_STALE_STATUS_TIMESTAMP, 'status_content_freshness_ms': status_content_freshness_ms, 'threshold_ms': stale_threshold_ms})
        elif universe_stale:
            effective_risk = _block_open_risk_result(build_reason(REASON_STALE_UNIVERSE_TIMESTAMP, 'stale universe blocks new entry', universe_content_freshness_ms=universe_content_freshness_ms, threshold_ms=stale_threshold_ms))
            log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.VALIDATION.value, message='new OPEN blocked due to stale universe', context={'reason': REASON_STALE_UNIVERSE_TIMESTAMP, 'universe_content_freshness_ms': universe_content_freshness_ms, 'threshold_ms': stale_threshold_ms})
        elif instance_memory.instance_state.duplicate_position_anomaly:
            effective_risk = _block_open_risk_result(build_reason(REASON_INSTANCE_CONFLICT, 'duplicate magic positions anomaly blocks new OPEN'))
            log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.PROTOCOL.value, message='new OPEN blocked due to duplicate position anomaly', context={'reason': REASON_INSTANCE_CONFLICT})
        elif stale_bar_blocks_open:
            effective_risk = _block_open_risk_result(build_reason(REASON_DATA_INVALID, 'stale market bar blocks new OPEN', bar_content_freshness_ms=bar_freshness_ms, market_file_freshness_ms=market_freshness_ms, threshold_ms=stale_threshold_ms))
            log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.VALIDATION.value, message='new OPEN blocked due to stale market bar', context={'reason': REASON_DATA_INVALID, 'bar_content_freshness_ms': bar_freshness_ms, 'market_file_freshness_ms': market_freshness_ms, 'threshold_ms': stale_threshold_ms})
    log_decision(runtime.paths, instance, decision_result, effective_risk, timestamp_utc=resolved_timestamp, ai_meta=ai_meta)
    if timeout_guard.is_exceeded():
        _finalize_cycle_state(instance_memory=instance_memory, runtime=runtime, decision_result=decision_result, timestamp_utc=resolved_timestamp)
        return _abort_cycle_timeout(runtime=runtime, instance=instance, timeout_guard=timeout_guard, instance_memory=instance_memory)
    if runtime.allow_control_writes and (not management_executed_close) and should_execute_trade(runtime=runtime, decision_result=decision_result, risk_engine_result=effective_risk):
        if timeout_guard.is_exceeded():
            _finalize_cycle_state(instance_memory=instance_memory, runtime=runtime, decision_result=decision_result, timestamp_utc=resolved_timestamp)
            return _abort_cycle_timeout(runtime=runtime, instance=instance, timeout_guard=timeout_guard, instance_memory=instance_memory)
        trade_intended = True
        execution_started = time.monotonic()
        entry_preexisting_tickets = tuple(p.ticket for p in find_status_positions(status, instance))
        entry_execution = run_execution_engine(paths=runtime.paths, instance=instance, instance_state=instance_memory.instance_state, decision_result=decision_result, risk_engine_result=effective_risk, runtime=runtime.config.runtime, management_result=_noop_management_result(), timestamp_utc=resolved_timestamp, retry_alert_context=RetryAlertContext(logger=runtime.system_logger, instance=instance, operation='entry execution io'), position_last_bar_utc=market_data_utc, preexisting_tickets=entry_preexisting_tickets)
        entry_latency = int((time.monotonic() - execution_started) * 1000)
        ack_latency_ms = entry_latency if ack_latency_ms is None else ack_latency_ms + entry_latency
        execution_result = entry_execution
        control_published = bool(entry_execution.control_published) or control_published
        ack = entry_execution.ack_interpretation
        if ack is not None:
            if ack.is_timeout:
                execution_unknown = True
                # ACK timeout alone must NOT clear pending_execution_command_id.
            else:
                ack_received = True
                if ack.is_success:
                    if ack.ack_record is not None:
                        broker_execution_confirmed = is_valid_open_fill_ack(ack.ack_record)
                    else:
                        broker_execution_confirmed = True
                if ack.is_failed or ack.is_rejected:
                    execution_failed = True
        trade_executed = broker_execution_confirmed
    _finalize_cycle_state(instance_memory=instance_memory, runtime=runtime, decision_result=decision_result, timestamp_utc=resolved_timestamp)
    timings = _build_cycle_timings(cycle_started=cycle_started, load_duration_ms=load_duration_ms, analysis_duration_ms=analysis_duration_ms, decision_duration_ms=decision_duration_ms)
    cycle_timeout_logged = _enforce_cycle_duration_limit(runtime=runtime, instance=instance, cycle_duration_ms=timings.cycle_duration_ms)
    return InstanceCycleResult(instance=instance, timestamp_utc=resolved_timestamp, completed=not cycle_timeout_logged, error_logged=cycle_timeout_logged, decision_result=decision_result, risk_engine_result=effective_risk, decision_journal_logged=True, execution_result=execution_result, trade_executed=trade_executed, trade_intended=trade_intended, control_published=control_published, ack_received=ack_received, broker_execution_confirmed=broker_execution_confirmed, execution_failed=execution_failed, execution_unknown=execution_unknown, ack_latency_ms=ack_latency_ms, performance_timings=timings, market_data_utc=market_data_utc)
