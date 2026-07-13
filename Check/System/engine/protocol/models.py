from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any
from engine.protocol.identity import validate_account_id as _shared_validate_account_id, validate_magic as _shared_validate_magic, validate_symbol as _shared_validate_symbol
from engine.protocol.constants import AckStatus, ErrorType, LogLevel, MarketRegime, NewsImpactLevel, Side, SYSTEM_NAME, TIMEFRAME_M1, TradeEvent, is_supported_config_schema_version, is_supported_protocol_schema_version, is_supported_state_schema_version, is_universe_forbidden_field, is_valid_ack_status, is_valid_decision, is_valid_order_action, is_valid_risk_result
from engine.protocol.errors import ValidationError

def _require_non_empty_string(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f'{field_name} must be a string', module='protocol.models', context={'field': field_name, 'value_type': type(value).__name__})
    stripped = value.strip()
    if not stripped:
        raise ValidationError(f'{field_name} must not be empty', module='protocol.models', context={'field': field_name})
    return stripped

def _require_int(value: int, field_name: str, *, minimum: int | None=None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f'{field_name} must be an integer', module='protocol.models', context={'field': field_name, 'value_type': type(value).__name__})
    if minimum is not None and value < minimum:
        raise ValidationError(f'{field_name} must be >= {minimum}', module='protocol.models', context={'field': field_name, 'value': value, 'minimum': minimum})
    return value

def _require_number(value: float, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f'{field_name} must be a number', module='protocol.models', context={'field': field_name, 'value_type': type(value).__name__})
    return float(value)

def _require_bool(value: bool, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f'{field_name} must be a boolean', module='protocol.models', context={'field': field_name, 'value_type': type(value).__name__})
    return value

def _validate_magic(magic: int) -> int:
    return _shared_validate_magic(magic, 'protocol.models')

def _validate_account_id(account_id: str) -> str:
    return _shared_validate_account_id(account_id, 'protocol.models')

def _validate_symbol(symbol: str) -> str:
    return _shared_validate_symbol(symbol, 'protocol.models')

@dataclass(frozen=True)
class InstanceKey:
    account_id: str
    symbol: str
    magic: int

    def __post_init__(self) -> None:
        object.__setattr__(self, 'account_id', _validate_account_id(self.account_id))
        object.__setattr__(self, 'symbol', _validate_symbol(self.symbol))
        object.__setattr__(self, 'magic', _validate_magic(self.magic))

    def as_tuple(self) -> tuple[str, str, int]:
        return (self.account_id, self.symbol, self.magic)

    def matches(self, account_id: str, symbol: str, magic: int) -> bool:
        return self.account_id == account_id and self.symbol == symbol and (self.magic == magic)

    def to_dict(self) -> dict[str, str | int]:
        return {'account_id': self.account_id, 'symbol': self.symbol, 'magic': self.magic}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InstanceKey:
        return cls(account_id=str(data['account_id']), symbol=str(data['symbol']), magic=int(data['magic']))

@dataclass(frozen=True)
class SystemSection:
    name: str
    root_path: str
    timeframe: str

    def __post_init__(self) -> None:
        name = _require_non_empty_string(self.name, 'system.name')
        root_path = _require_non_empty_string(self.root_path, 'system.root_path')
        timeframe = _require_non_empty_string(self.timeframe, 'system.timeframe')
        if name != SYSTEM_NAME:
            raise ValidationError(f'system.name must be {SYSTEM_NAME}', module='protocol.models', context={'value': name})
        if timeframe != TIMEFRAME_M1:
            raise ValidationError(f'system.timeframe must be {TIMEFRAME_M1}', module='protocol.models', context={'value': timeframe})
        object.__setattr__(self, 'name', name)
        object.__setattr__(self, 'root_path', root_path)
        object.__setattr__(self, 'timeframe', timeframe)

    def to_dict(self) -> dict[str, str]:
        return {'name': self.name, 'root_path': self.root_path, 'timeframe': self.timeframe}

@dataclass(frozen=True)
class PathsConfig:
    clients: str
    logs: str
    cache: str
    history: str
    universe: str

    def __post_init__(self) -> None:
        object.__setattr__(self, 'clients', _require_non_empty_string(self.clients, 'paths.clients'))
        object.__setattr__(self, 'logs', _require_non_empty_string(self.logs, 'paths.logs'))
        object.__setattr__(self, 'cache', _require_non_empty_string(self.cache, 'paths.cache'))
        object.__setattr__(self, 'history', _require_non_empty_string(self.history, 'paths.history'))
        object.__setattr__(self, 'universe', _require_non_empty_string(self.universe, 'paths.universe'))

    def to_dict(self) -> dict[str, str]:
        return {'clients': self.clients, 'logs': self.logs, 'cache': self.cache, 'history': self.history, 'universe': self.universe}

@dataclass(frozen=True)
class RuntimeConfig:
    cycle_interval_ms: int
    ack_timeout_ms: int
    retry_max: int
    retry_delay_ms: int
    data_stale_threshold_ms: int
    cycle_max_duration_ms: int
    metrics_interval_ms: int
    auto_discover_instances: bool
    execute_entries_on_closed_bar_only: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, 'cycle_interval_ms', _require_int(self.cycle_interval_ms, 'runtime.cycle_interval_ms', minimum=1))
        object.__setattr__(self, 'ack_timeout_ms', _require_int(self.ack_timeout_ms, 'runtime.ack_timeout_ms', minimum=1))
        object.__setattr__(self, 'retry_max', _require_int(self.retry_max, 'runtime.retry_max', minimum=0))
        object.__setattr__(self, 'retry_delay_ms', _require_int(self.retry_delay_ms, 'runtime.retry_delay_ms', minimum=0))
        object.__setattr__(self, 'data_stale_threshold_ms', _require_int(self.data_stale_threshold_ms, 'runtime.data_stale_threshold_ms', minimum=1))
        object.__setattr__(self, 'cycle_max_duration_ms', _require_int(self.cycle_max_duration_ms, 'runtime.cycle_max_duration_ms', minimum=1))
        object.__setattr__(self, 'metrics_interval_ms', _require_int(self.metrics_interval_ms, 'runtime.metrics_interval_ms', minimum=1))
        object.__setattr__(self, 'auto_discover_instances', _require_bool(self.auto_discover_instances, 'runtime.auto_discover_instances'))
        object.__setattr__(self, 'execute_entries_on_closed_bar_only', _require_bool(self.execute_entries_on_closed_bar_only, 'runtime.execute_entries_on_closed_bar_only'))

    def to_dict(self) -> dict[str, int | bool]:
        return {'cycle_interval_ms': self.cycle_interval_ms, 'ack_timeout_ms': self.ack_timeout_ms, 'retry_max': self.retry_max, 'retry_delay_ms': self.retry_delay_ms, 'data_stale_threshold_ms': self.data_stale_threshold_ms, 'cycle_max_duration_ms': self.cycle_max_duration_ms, 'metrics_interval_ms': self.metrics_interval_ms, 'auto_discover_instances': self.auto_discover_instances, 'execute_entries_on_closed_bar_only': self.execute_entries_on_closed_bar_only}

@dataclass(frozen=True)
class InstanceDefinition:
    account_id: str
    symbol: str
    magic: int
    enabled: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, 'account_id', _validate_account_id(self.account_id))
        object.__setattr__(self, 'symbol', _validate_symbol(self.symbol))
        object.__setattr__(self, 'magic', _validate_magic(self.magic))
        object.__setattr__(self, 'enabled', _require_bool(self.enabled, 'instances[].enabled'))

    @property
    def instance_key(self) -> InstanceKey:
        return InstanceKey(self.account_id, self.symbol, self.magic)

    def to_dict(self) -> dict[str, str | int | bool]:
        return {'account_id': self.account_id, 'symbol': self.symbol, 'magic': self.magic, 'enabled': self.enabled}
ANALYSIS_WEIGHT_KEYS: tuple[str, ...] = ('momentum', 'trend', 'structure', 'pressure', 'behavior', 'impact', 'context')

@dataclass(frozen=True)
class AnalysisWeights:
    momentum: float
    trend: float
    structure: float
    pressure: float
    behavior: float
    impact: float
    context: float

    def __post_init__(self) -> None:
        for field_name in ANALYSIS_WEIGHT_KEYS:
            value = getattr(self, field_name)
            normalized = _require_number(value, f'analysis.weights.{field_name}')
            if normalized < 0:
                raise ValidationError(f'analysis.weights.{field_name} must be >= 0', module='protocol.models', context={'field': field_name, 'value': normalized})
            object.__setattr__(self, field_name, normalized)

    def as_mapping(self) -> dict[str, float]:
        return {field_name: getattr(self, field_name) for field_name in ANALYSIS_WEIGHT_KEYS}

    def to_dict(self) -> dict[str, float]:
        return self.as_mapping()

@dataclass(frozen=True)
class RiskConfig:
    max_open_positions_per_instance: int
    max_daily_loss_percent: float
    max_drawdown_percent: float
    daily_loss_limit_enabled: bool
    drawdown_limit_enabled: bool
    reward_ratio: float
    max_risk_per_trade_percent: float
    max_stop_loss_pips: float
    volume_step: float
    fixed_lot_volume: float

    def __post_init__(self) -> None:
        object.__setattr__(self, 'max_open_positions_per_instance', _require_int(self.max_open_positions_per_instance, 'risk.max_open_positions_per_instance', minimum=0))
        object.__setattr__(self, 'max_daily_loss_percent', _require_number(self.max_daily_loss_percent, 'risk.max_daily_loss_percent'))
        object.__setattr__(self, 'max_drawdown_percent', _require_number(self.max_drawdown_percent, 'risk.max_drawdown_percent'))
        object.__setattr__(self, 'daily_loss_limit_enabled', _require_bool(self.daily_loss_limit_enabled, 'risk.daily_loss_limit_enabled'))
        object.__setattr__(self, 'drawdown_limit_enabled', _require_bool(self.drawdown_limit_enabled, 'risk.drawdown_limit_enabled'))
        reward_ratio = _require_number(self.reward_ratio, 'risk.reward_ratio')
        if reward_ratio <= 0:
            raise ValidationError('risk.reward_ratio must be > 0', module='protocol.models', context={'value': reward_ratio})
        object.__setattr__(self, 'reward_ratio', reward_ratio)
        max_risk_per_trade_percent = _require_number(self.max_risk_per_trade_percent, 'risk.max_risk_per_trade_percent')
        if max_risk_per_trade_percent <= 0:
            raise ValidationError('risk.max_risk_per_trade_percent must be > 0', module='protocol.models', context={'value': max_risk_per_trade_percent})
        object.__setattr__(self, 'max_risk_per_trade_percent', max_risk_per_trade_percent)
        max_stop_loss_pips = _require_number(self.max_stop_loss_pips, 'risk.max_stop_loss_pips')
        if max_stop_loss_pips <= 0:
            raise ValidationError('risk.max_stop_loss_pips must be > 0', module='protocol.models', context={'value': max_stop_loss_pips})
        object.__setattr__(self, 'max_stop_loss_pips', max_stop_loss_pips)
        volume_step = _require_number(self.volume_step, 'risk.volume_step')
        if volume_step <= 0:
            raise ValidationError('risk.volume_step must be > 0', module='protocol.models', context={'value': volume_step})
        object.__setattr__(self, 'volume_step', volume_step)
        fixed_lot_volume = _require_number(self.fixed_lot_volume, 'risk.fixed_lot_volume')
        if fixed_lot_volume < 0:
            raise ValidationError('risk.fixed_lot_volume must be >= 0', module='protocol.models', context={'value': fixed_lot_volume})
        object.__setattr__(self, 'fixed_lot_volume', fixed_lot_volume)

    def to_dict(self) -> dict[str, int | float | bool]:
        return {'max_open_positions_per_instance': self.max_open_positions_per_instance, 'max_daily_loss_percent': self.max_daily_loss_percent, 'max_drawdown_percent': self.max_drawdown_percent, 'daily_loss_limit_enabled': self.daily_loss_limit_enabled, 'drawdown_limit_enabled': self.drawdown_limit_enabled, 'reward_ratio': self.reward_ratio, 'max_risk_per_trade_percent': self.max_risk_per_trade_percent, 'max_stop_loss_pips': self.max_stop_loss_pips, 'volume_step': self.volume_step, 'fixed_lot_volume': self.fixed_lot_volume}

@dataclass(frozen=True)
class AnalysisConfig:
    lookback_bars: int
    structure_lookback_bars: int
    spread_relative_threshold: float
    volatility_relative_threshold: float
    block_high_impact_news: bool
    stop_loss_buffer: float
    block_ranging_chase_entries: bool
    ranging_extreme_threshold: float
    ranging_recent_momentum_bars: int
    weights: AnalysisWeights

    def __post_init__(self) -> None:
        object.__setattr__(self, 'lookback_bars', _require_int(self.lookback_bars, 'analysis.lookback_bars', minimum=1))
        structure_lookback_bars = _require_int(self.structure_lookback_bars, 'analysis.structure_lookback_bars', minimum=1)
        if structure_lookback_bars > self.lookback_bars:
            raise ValidationError('analysis.structure_lookback_bars must be <= analysis.lookback_bars', module='protocol.models', context={'structure_lookback_bars': structure_lookback_bars, 'lookback_bars': self.lookback_bars})
        object.__setattr__(self, 'structure_lookback_bars', structure_lookback_bars)
        spread_relative_threshold = _require_number(self.spread_relative_threshold, 'analysis.spread_relative_threshold')
        if spread_relative_threshold <= 0:
            raise ValidationError('analysis.spread_relative_threshold must be > 0', module='protocol.models', context={'value': spread_relative_threshold})
        object.__setattr__(self, 'spread_relative_threshold', spread_relative_threshold)
        volatility_relative_threshold = _require_number(self.volatility_relative_threshold, 'analysis.volatility_relative_threshold')
        if volatility_relative_threshold <= 0:
            raise ValidationError('analysis.volatility_relative_threshold must be > 0', module='protocol.models', context={'value': volatility_relative_threshold})
        object.__setattr__(self, 'volatility_relative_threshold', volatility_relative_threshold)
        object.__setattr__(self, 'block_high_impact_news', _require_bool(self.block_high_impact_news, 'analysis.block_high_impact_news'))
        stop_loss_buffer = _require_number(self.stop_loss_buffer, 'analysis.stop_loss_buffer')
        if stop_loss_buffer < 0:
            raise ValidationError('analysis.stop_loss_buffer must be >= 0', module='protocol.models', context={'value': stop_loss_buffer})
        object.__setattr__(self, 'stop_loss_buffer', stop_loss_buffer)
        object.__setattr__(self, 'block_ranging_chase_entries', _require_bool(self.block_ranging_chase_entries, 'analysis.block_ranging_chase_entries'))
        ranging_extreme_threshold = _require_number(self.ranging_extreme_threshold, 'analysis.ranging_extreme_threshold')
        if ranging_extreme_threshold <= 0 or ranging_extreme_threshold >= 1:
            raise ValidationError('analysis.ranging_extreme_threshold must be between 0 and 1', module='protocol.models', context={'value': ranging_extreme_threshold})
        object.__setattr__(self, 'ranging_extreme_threshold', ranging_extreme_threshold)
        ranging_recent_momentum_bars = _require_int(self.ranging_recent_momentum_bars, 'analysis.ranging_recent_momentum_bars', minimum=1)
        if ranging_recent_momentum_bars > self.lookback_bars:
            raise ValidationError('analysis.ranging_recent_momentum_bars must be <= analysis.lookback_bars', module='protocol.models', context={'ranging_recent_momentum_bars': ranging_recent_momentum_bars, 'lookback_bars': self.lookback_bars})
        object.__setattr__(self, 'ranging_recent_momentum_bars', ranging_recent_momentum_bars)
        if not isinstance(self.weights, AnalysisWeights):
            raise ValidationError('analysis.weights must be an AnalysisWeights instance', module='protocol.models', context={'value_type': type(self.weights).__name__})

    def to_dict(self) -> dict[str, int | float | bool | dict[str, float]]:
        return {'lookback_bars': self.lookback_bars, 'structure_lookback_bars': self.structure_lookback_bars, 'spread_relative_threshold': self.spread_relative_threshold, 'volatility_relative_threshold': self.volatility_relative_threshold, 'block_high_impact_news': self.block_high_impact_news, 'stop_loss_buffer': self.stop_loss_buffer, 'block_ranging_chase_entries': self.block_ranging_chase_entries, 'ranging_extreme_threshold': self.ranging_extreme_threshold, 'ranging_recent_momentum_bars': self.ranging_recent_momentum_bars, 'weights': self.weights.to_dict()}

@dataclass(frozen=True)
class TradeManagementSettings:
    enabled: bool
    allow_close: bool
    use_fixed_take_profit: bool
    breakeven_progress_ratio: float
    partial_close_progress_ratio: float
    partial_close_volume_ratio: float
    time_stop_max_bars: int

    def __post_init__(self) -> None:
        object.__setattr__(self, 'enabled', _require_bool(self.enabled, 'trade_management.enabled'))
        object.__setattr__(self, 'allow_close', _require_bool(self.allow_close, 'trade_management.allow_close'))
        object.__setattr__(self, 'use_fixed_take_profit', _require_bool(self.use_fixed_take_profit, 'trade_management.use_fixed_take_profit'))
        breakeven_progress_ratio = _require_number(self.breakeven_progress_ratio, 'trade_management.breakeven_progress_ratio')
        if not 0 < breakeven_progress_ratio <= 1:
            raise ValidationError('trade_management.breakeven_progress_ratio must be in (0, 1]', module='protocol.models', context={'value': breakeven_progress_ratio})
        object.__setattr__(self, 'breakeven_progress_ratio', breakeven_progress_ratio)
        partial_close_progress_ratio = _require_number(self.partial_close_progress_ratio, 'trade_management.partial_close_progress_ratio')
        if not 0 < partial_close_progress_ratio <= 1:
            raise ValidationError('trade_management.partial_close_progress_ratio must be in (0, 1]', module='protocol.models', context={'value': partial_close_progress_ratio})
        object.__setattr__(self, 'partial_close_progress_ratio', partial_close_progress_ratio)
        partial_close_volume_ratio = _require_number(self.partial_close_volume_ratio, 'trade_management.partial_close_volume_ratio')
        if not 0 < partial_close_volume_ratio < 1:
            raise ValidationError('trade_management.partial_close_volume_ratio must be in (0, 1)', module='protocol.models', context={'value': partial_close_volume_ratio})
        object.__setattr__(self, 'partial_close_volume_ratio', partial_close_volume_ratio)
        object.__setattr__(self, 'time_stop_max_bars', _require_int(self.time_stop_max_bars, 'trade_management.time_stop_max_bars', minimum=1))

    def to_dict(self) -> dict[str, int | float | bool]:
        return {'enabled': self.enabled, 'allow_close': self.allow_close, 'use_fixed_take_profit': self.use_fixed_take_profit, 'breakeven_progress_ratio': self.breakeven_progress_ratio, 'partial_close_progress_ratio': self.partial_close_progress_ratio, 'partial_close_volume_ratio': self.partial_close_volume_ratio, 'time_stop_max_bars': self.time_stop_max_bars}

@dataclass(frozen=True)
class JournalConfig:
    retention_days: int

    def __post_init__(self) -> None:
        object.__setattr__(self, 'retention_days', _require_int(self.retention_days, 'journal.retention_days', minimum=1))

    def to_dict(self) -> dict[str, int]:
        return {'retention_days': self.retention_days}

@dataclass(frozen=True)
class DashboardConfig:
    refresh_interval_ms: int

    def __post_init__(self) -> None:
        object.__setattr__(self, 'refresh_interval_ms', _require_int(self.refresh_interval_ms, 'dashboard.refresh_interval_ms', minimum=1))

    def to_dict(self) -> dict[str, int]:
        return {'refresh_interval_ms': self.refresh_interval_ms}

@dataclass(frozen=True)
class LoggingConfig:
    level: str
    format: str

    def __post_init__(self) -> None:
        level = _require_non_empty_string(self.level, 'logging.level')
        log_format = _require_non_empty_string(self.format, 'logging.format')
        if level not in LogLevel._value2member_map_:
            raise ValidationError('logging.level is invalid', module='protocol.models', context={'value': level})
        object.__setattr__(self, 'level', level)
        object.__setattr__(self, 'format', log_format)

    def to_dict(self) -> dict[str, str]:
        return {'level': self.level, 'format': self.format}
_AI_MODES = frozenset({'advisory', 'required', 'off'})
_AI_REJECT_ACTIONS = frozenset({'BLOCK', 'WAIT'})

@dataclass(frozen=True)
class AIConfig:
    mode: str
    fail_closed: bool
    reject_action: str
    timeout_ms: int
    retry_max: int
    retry_delay_ms: int

    def __post_init__(self) -> None:
        mode = _require_non_empty_string(self.mode, 'ai.mode')
        if mode not in _AI_MODES:
            raise ValidationError('ai.mode is invalid', module='protocol.models', context={'value': mode, 'allowed': sorted(_AI_MODES)})
        reject_action = _require_non_empty_string(self.reject_action, 'ai.reject_action')
        if reject_action not in _AI_REJECT_ACTIONS:
            raise ValidationError('ai.reject_action is invalid', module='protocol.models', context={'value': reject_action, 'allowed': sorted(_AI_REJECT_ACTIONS)})
        object.__setattr__(self, 'mode', mode)
        object.__setattr__(self, 'fail_closed', _require_bool(self.fail_closed, 'ai.fail_closed'))
        object.__setattr__(self, 'reject_action', reject_action)
        object.__setattr__(self, 'timeout_ms', _require_int(self.timeout_ms, 'ai.timeout_ms', minimum=1))
        object.__setattr__(self, 'retry_max', _require_int(self.retry_max, 'ai.retry_max', minimum=0))
        object.__setattr__(self, 'retry_delay_ms', _require_int(self.retry_delay_ms, 'ai.retry_delay_ms', minimum=0))

    def to_dict(self) -> dict[str, Any]:
        return {'mode': self.mode, 'fail_closed': self.fail_closed, 'reject_action': self.reject_action, 'timeout_ms': self.timeout_ms, 'retry_max': self.retry_max, 'retry_delay_ms': self.retry_delay_ms}

@dataclass(frozen=True)
class SystemConfig:
    schema_version: str
    system: SystemSection
    paths: PathsConfig
    runtime: RuntimeConfig
    instances: tuple[InstanceDefinition, ...]
    risk: RiskConfig
    analysis: AnalysisConfig
    journal: JournalConfig
    trade_management: TradeManagementSettings
    dashboard: DashboardConfig
    logging: LoggingConfig
    ai: AIConfig

    def __post_init__(self) -> None:
        schema_version = _require_non_empty_string(self.schema_version, 'schema_version')
        if not is_supported_config_schema_version(schema_version):
            raise ValidationError('unsupported config schema_version', module='protocol.models', context={'schema_version': schema_version})
        if not isinstance(self.instances, tuple):
            raise ValidationError('instances must be a tuple', module='protocol.models', context={'value_type': type(self.instances).__name__})
        keys = [instance.instance_key.as_tuple() for instance in self.instances]
        if len(keys) != len(set(keys)):
            raise ValidationError('duplicate instance definitions are not allowed', module='protocol.models', context={'instances': list(keys)})
        object.__setattr__(self, 'schema_version', schema_version)

    def to_dict(self) -> dict[str, Any]:
        return {'schema_version': self.schema_version, 'system': self.system.to_dict(), 'paths': self.paths.to_dict(), 'runtime': self.runtime.to_dict(), 'instances': [instance.to_dict() for instance in self.instances], 'risk': self.risk.to_dict(), 'analysis': self.analysis.to_dict(), 'journal': self.journal.to_dict(), 'trade_management': self.trade_management.to_dict(), 'dashboard': self.dashboard.to_dict(), 'logging': self.logging.to_dict(), 'ai': self.ai.to_dict()}

@dataclass(frozen=True)
class StatusPositionSnapshot:
    symbol: str
    magic: int
    ticket: int
    side: str
    volume: float
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'symbol', _validate_symbol(self.symbol))
        object.__setattr__(self, 'magic', _validate_magic(self.magic))
        object.__setattr__(self, 'ticket', _require_int(self.ticket, 'open_positions.ticket', minimum=0))
        side = _require_non_empty_string(self.side, 'open_positions.side')
        if side not in {Side.BUY.value, Side.SELL.value}:
            raise ValidationError('open_positions.side must be BUY or SELL', module='protocol.models', context={'value': side})
        object.__setattr__(self, 'side', side)
        volume = _require_number(self.volume, 'open_positions.volume')
        if volume <= 0:
            raise ValidationError('open_positions.volume must be > 0', module='protocol.models', context={'value': volume})
        object.__setattr__(self, 'volume', volume)
        if self.entry_price is not None:
            object.__setattr__(self, 'entry_price', _require_number(self.entry_price, 'open_positions.entry_price'))
        if self.stop_loss is not None:
            object.__setattr__(self, 'stop_loss', _require_number(self.stop_loss, 'open_positions.stop_loss'))
        if self.take_profit is not None:
            object.__setattr__(self, 'take_profit', _require_number(self.take_profit, 'open_positions.take_profit'))

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {'symbol': self.symbol, 'magic': self.magic, 'ticket': self.ticket, 'side': self.side, 'volume': self.volume}
        if self.entry_price is not None:
            data['entry_price'] = self.entry_price
        if self.stop_loss is not None:
            data['stop_loss'] = self.stop_loss
        if self.take_profit is not None:
            data['take_profit'] = self.take_profit
        return data

@dataclass(frozen=True)
class StatusRecord:
    schema_version: str
    timestamp_utc: str
    account_id: str
    connected: bool
    trade_allowed: bool
    balance: float
    equity: float
    margin_free: float
    ea_version: str
    last_error: str | None = None
    open_positions: tuple[StatusPositionSnapshot, ...] = ()

    def __post_init__(self) -> None:
        schema_version = _require_non_empty_string(self.schema_version, 'schema_version')
        if not is_supported_protocol_schema_version(schema_version):
            raise ValidationError('unsupported protocol schema_version', module='protocol.models', context={'schema_version': schema_version})
        object.__setattr__(self, 'schema_version', schema_version)
        object.__setattr__(self, 'timestamp_utc', _require_non_empty_string(self.timestamp_utc, 'timestamp_utc'))
        object.__setattr__(self, 'account_id', _validate_account_id(self.account_id))
        object.__setattr__(self, 'connected', _require_bool(self.connected, 'connected'))
        object.__setattr__(self, 'trade_allowed', _require_bool(self.trade_allowed, 'trade_allowed'))
        object.__setattr__(self, 'balance', _require_number(self.balance, 'balance'))
        object.__setattr__(self, 'equity', _require_number(self.equity, 'equity'))
        object.__setattr__(self, 'margin_free', _require_number(self.margin_free, 'margin_free'))
        object.__setattr__(self, 'ea_version', _require_non_empty_string(self.ea_version, 'ea_version'))
        if self.last_error is not None:
            object.__setattr__(self, 'last_error', _require_non_empty_string(self.last_error, 'last_error'))
        if not isinstance(self.open_positions, tuple):
            raise ValidationError('open_positions must be a tuple', module='protocol.models', context={'value_type': type(self.open_positions).__name__})
        for position in self.open_positions:
            if not isinstance(position, StatusPositionSnapshot):
                raise ValidationError('open_positions entries must be StatusPositionSnapshot', module='protocol.models', context={'value_type': type(position).__name__})

    def to_dict(self) -> dict[str, Any]:
        data = {'schema_version': self.schema_version, 'timestamp_utc': self.timestamp_utc, 'account_id': self.account_id, 'connected': self.connected, 'trade_allowed': self.trade_allowed, 'balance': self.balance, 'equity': self.equity, 'margin_free': self.margin_free, 'ea_version': self.ea_version}
        if self.last_error is not None:
            data['last_error'] = self.last_error
        if self.open_positions:
            data['open_positions'] = [position.to_dict() for position in self.open_positions]
        return data

@dataclass(frozen=True)
class UniverseRecord:
    schema_version: str
    timestamp_utc: str
    session: str
    market_regime: str
    news_window_active: bool
    news_impact_level: str | None = None
    correlation_group: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        schema_version = _require_non_empty_string(self.schema_version, 'schema_version')
        if not is_supported_protocol_schema_version(schema_version):
            raise ValidationError('unsupported protocol schema_version', module='protocol.models', context={'schema_version': schema_version})
        object.__setattr__(self, 'schema_version', schema_version)
        object.__setattr__(self, 'timestamp_utc', _require_non_empty_string(self.timestamp_utc, 'timestamp_utc'))
        object.__setattr__(self, 'session', _require_non_empty_string(self.session, 'session'))
        market_regime = _require_non_empty_string(self.market_regime, 'market_regime')
        if market_regime not in MarketRegime._value2member_map_:
            raise ValidationError('market_regime is invalid', module='protocol.models', context={'value': market_regime})
        object.__setattr__(self, 'market_regime', market_regime)
        object.__setattr__(self, 'news_window_active', _require_bool(self.news_window_active, 'news_window_active'))
        if self.news_impact_level is not None:
            impact = _require_non_empty_string(self.news_impact_level, 'news_impact_level')
            if impact not in NewsImpactLevel._value2member_map_:
                raise ValidationError('news_impact_level is invalid', module='protocol.models', context={'value': impact})
            object.__setattr__(self, 'news_impact_level', impact)
        if self.correlation_group is not None and (not isinstance(self.correlation_group, dict)):
            raise ValidationError('correlation_group must be a dict', module='protocol.models')
        if self.metadata is not None:
            if not isinstance(self.metadata, dict):
                raise ValidationError('metadata must be a dict', module='protocol.models')
            for key in self.metadata:
                if is_universe_forbidden_field(key):
                    raise ValidationError(f'universe metadata contains forbidden field: {key}', module='protocol.models', context={'field': key})

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {'schema_version': self.schema_version, 'timestamp_utc': self.timestamp_utc, 'session': self.session, 'market_regime': self.market_regime, 'news_window_active': self.news_window_active}
        if self.news_impact_level is not None:
            data['news_impact_level'] = self.news_impact_level
        if self.correlation_group is not None:
            data['correlation_group'] = self.correlation_group
        if self.metadata is not None:
            data['metadata'] = self.metadata
        return data

@dataclass(frozen=True)
class ControlCommand:
    schema_version: str
    timestamp_utc: str
    command_id: str
    account_id: str
    symbol: str
    magic: int
    action: str
    reason: str
    decision_id: str
    side: str | None = None
    volume: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    ticket: int | None = None

    def __post_init__(self) -> None:
        schema_version = _require_non_empty_string(self.schema_version, 'schema_version')
        if not is_supported_protocol_schema_version(schema_version):
            raise ValidationError('unsupported protocol schema_version', module='protocol.models', context={'schema_version': schema_version})
        object.__setattr__(self, 'schema_version', schema_version)
        object.__setattr__(self, 'timestamp_utc', _require_non_empty_string(self.timestamp_utc, 'timestamp_utc'))
        object.__setattr__(self, 'command_id', _require_non_empty_string(self.command_id, 'command_id'))
        object.__setattr__(self, 'account_id', _validate_account_id(self.account_id))
        object.__setattr__(self, 'symbol', _validate_symbol(self.symbol))
        object.__setattr__(self, 'magic', _validate_magic(self.magic))
        action = _require_non_empty_string(self.action, 'action')
        if not is_valid_order_action(action):
            raise ValidationError('action is invalid', module='protocol.models', context={'value': action})
        object.__setattr__(self, 'action', action)
        object.__setattr__(self, 'reason', _require_non_empty_string(self.reason, 'reason'))
        object.__setattr__(self, 'decision_id', _require_non_empty_string(self.decision_id, 'decision_id'))
        if self.side is not None:
            side = _require_non_empty_string(self.side, 'side')
            if side not in {Side.BUY.value, Side.SELL.value}:
                raise ValidationError('side is invalid', module='protocol.models', context={'value': side})
            object.__setattr__(self, 'side', side)
        if self.volume is not None:
            object.__setattr__(self, 'volume', _require_number(self.volume, 'volume'))
        if self.stop_loss is not None:
            object.__setattr__(self, 'stop_loss', _require_number(self.stop_loss, 'stop_loss'))
        if self.take_profit is not None:
            object.__setattr__(self, 'take_profit', _require_number(self.take_profit, 'take_profit'))
        if self.ticket is not None:
            object.__setattr__(self, 'ticket', _require_int(self.ticket, 'ticket', minimum=0))

    @property
    def instance_key(self) -> InstanceKey:
        return InstanceKey(self.account_id, self.symbol, self.magic)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {'schema_version': self.schema_version, 'timestamp_utc': self.timestamp_utc, 'command_id': self.command_id, 'account_id': self.account_id, 'symbol': self.symbol, 'magic': self.magic, 'action': self.action, 'reason': self.reason, 'decision_id': self.decision_id}
        if self.side is not None:
            data['side'] = self.side
        if self.volume is not None:
            data['volume'] = self.volume
        if self.stop_loss is not None:
            data['stop_loss'] = self.stop_loss
        if self.take_profit is not None:
            data['take_profit'] = self.take_profit
        if self.ticket is not None:
            data['ticket'] = self.ticket
        return data

@dataclass(frozen=True)
class AckRecord:
    schema_version: str
    timestamp_utc: str
    command_id: str
    account_id: str
    symbol: str
    magic: int
    status: str
    ticket: int | None = None
    error_code: int | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        schema_version = _require_non_empty_string(self.schema_version, 'schema_version')
        if not is_supported_protocol_schema_version(schema_version):
            raise ValidationError('unsupported protocol schema_version', module='protocol.models', context={'schema_version': schema_version})
        object.__setattr__(self, 'schema_version', schema_version)
        object.__setattr__(self, 'timestamp_utc', _require_non_empty_string(self.timestamp_utc, 'timestamp_utc'))
        object.__setattr__(self, 'command_id', _require_non_empty_string(self.command_id, 'command_id'))
        object.__setattr__(self, 'account_id', _validate_account_id(self.account_id))
        object.__setattr__(self, 'symbol', _validate_symbol(self.symbol))
        object.__setattr__(self, 'magic', _validate_magic(self.magic))
        status = _require_non_empty_string(self.status, 'status')
        if not is_valid_ack_status(status):
            raise ValidationError('status is invalid', module='protocol.models', context={'value': status})
        object.__setattr__(self, 'status', status)
        if self.ticket is not None:
            object.__setattr__(self, 'ticket', _require_int(self.ticket, 'ticket', minimum=0))
        if self.error_code is not None:
            object.__setattr__(self, 'error_code', _require_int(self.error_code, 'error_code'))
        if self.error_message is not None:
            object.__setattr__(self, 'error_message', _require_non_empty_string(self.error_message, 'error_message'))

    @property
    def instance_key(self) -> InstanceKey:
        return InstanceKey(self.account_id, self.symbol, self.magic)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {'schema_version': self.schema_version, 'timestamp_utc': self.timestamp_utc, 'command_id': self.command_id, 'account_id': self.account_id, 'symbol': self.symbol, 'magic': self.magic, 'status': self.status}
        if self.ticket is not None:
            data['ticket'] = self.ticket
        if self.error_code is not None:
            data['error_code'] = self.error_code
        if self.error_message is not None:
            data['error_message'] = self.error_message
        return data

@dataclass(frozen=True)
class InstanceStateRecord:
    schema_version: str
    account_id: str
    symbol: str
    magic: int
    last_decision: str
    last_reason: str
    last_command_id: str
    last_ack_status: str
    instrument_digits: int
    instrument_point: float
    instrument_pip: float
    cycle_count: int
    last_cycle_utc: str
    open_ticket: int | None = None
    position_side: str | None = None
    position_volume: float | None = None

    def __post_init__(self) -> None:
        schema_version = _require_non_empty_string(self.schema_version, 'schema_version')
        if not is_supported_state_schema_version(schema_version):
            raise ValidationError('unsupported state schema_version', module='protocol.models', context={'schema_version': schema_version})
        object.__setattr__(self, 'schema_version', schema_version)
        object.__setattr__(self, 'account_id', _validate_account_id(self.account_id))
        object.__setattr__(self, 'symbol', _validate_symbol(self.symbol))
        object.__setattr__(self, 'magic', _validate_magic(self.magic))
        last_decision = _require_non_empty_string(self.last_decision, 'last_decision')
        if not is_valid_decision(last_decision):
            raise ValidationError('last_decision is invalid', module='protocol.models', context={'value': last_decision})
        object.__setattr__(self, 'last_decision', last_decision)
        object.__setattr__(self, 'last_reason', _require_non_empty_string(self.last_reason, 'last_reason'))
        if not isinstance(self.last_command_id, str):
            raise ValidationError('last_command_id must be a string', module='protocol.models', context={'value_type': type(self.last_command_id).__name__})
        object.__setattr__(self, 'last_command_id', self.last_command_id)
        last_ack_status = _require_non_empty_string(self.last_ack_status, 'last_ack_status')
        if last_ack_status not in AckStatus._value2member_map_:
            raise ValidationError('last_ack_status is invalid', module='protocol.models', context={'value': last_ack_status})
        object.__setattr__(self, 'last_ack_status', last_ack_status)
        instrument_digits = _require_int(self.instrument_digits, 'instrument_digits', minimum=0)
        object.__setattr__(self, 'instrument_digits', instrument_digits)
        instrument_point = _require_number(self.instrument_point, 'instrument_point')
        if instrument_point < 0:
            raise ValidationError('instrument_point must be >= 0', module='protocol.models', context={'value': instrument_point})
        object.__setattr__(self, 'instrument_point', instrument_point)
        instrument_pip = _require_number(self.instrument_pip, 'instrument_pip')
        if instrument_pip < 0:
            raise ValidationError('instrument_pip must be >= 0', module='protocol.models', context={'value': instrument_pip})
        object.__setattr__(self, 'instrument_pip', instrument_pip)
        cycle_count = _require_int(self.cycle_count, 'cycle_count', minimum=0)
        object.__setattr__(self, 'cycle_count', cycle_count)
        object.__setattr__(self, 'last_cycle_utc', _require_non_empty_string(self.last_cycle_utc, 'last_cycle_utc'))
        if self.open_ticket is not None:
            object.__setattr__(self, 'open_ticket', _require_int(self.open_ticket, 'open_ticket', minimum=0))
        if self.position_side is not None:
            side = _require_non_empty_string(self.position_side, 'position_side')
            if side not in {Side.BUY.value, Side.SELL.value}:
                raise ValidationError('position_side is invalid', module='protocol.models', context={'value': side})
            object.__setattr__(self, 'position_side', side)
        if self.position_volume is not None:
            object.__setattr__(self, 'position_volume', _require_number(self.position_volume, 'position_volume'))

    @property
    def instance_key(self) -> InstanceKey:
        return InstanceKey(self.account_id, self.symbol, self.magic)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {'schema_version': self.schema_version, 'account_id': self.account_id, 'symbol': self.symbol, 'magic': self.magic, 'last_decision': self.last_decision, 'last_reason': self.last_reason, 'last_command_id': self.last_command_id, 'last_ack_status': self.last_ack_status, 'instrument_digits': self.instrument_digits, 'instrument_point': self.instrument_point, 'instrument_pip': self.instrument_pip, 'cycle_count': self.cycle_count, 'last_cycle_utc': self.last_cycle_utc}
        if self.open_ticket is not None:
            data['open_ticket'] = self.open_ticket
        if self.position_side is not None:
            data['position_side'] = self.position_side
        if self.position_volume is not None:
            data['position_volume'] = self.position_volume
        return data

@dataclass(frozen=True)
class SpreadStateRecord:
    schema_version: str
    account_id: str
    symbol: str
    magic: int
    sample_count: int
    mean_spread: float
    std_spread: float
    median_spread: float
    current_spread: float
    relative_spread: float
    updated_utc: str

    def __post_init__(self) -> None:
        schema_version = _require_non_empty_string(self.schema_version, 'schema_version')
        if not is_supported_state_schema_version(schema_version):
            raise ValidationError('unsupported state schema_version', module='protocol.models', context={'schema_version': schema_version})
        object.__setattr__(self, 'schema_version', schema_version)
        object.__setattr__(self, 'account_id', _validate_account_id(self.account_id))
        object.__setattr__(self, 'symbol', _validate_symbol(self.symbol))
        object.__setattr__(self, 'magic', _validate_magic(self.magic))
        object.__setattr__(self, 'sample_count', _require_int(self.sample_count, 'sample_count', minimum=0))
        object.__setattr__(self, 'mean_spread', _require_number(self.mean_spread, 'mean_spread'))
        object.__setattr__(self, 'std_spread', _require_number(self.std_spread, 'std_spread'))
        object.__setattr__(self, 'median_spread', _require_number(self.median_spread, 'median_spread'))
        object.__setattr__(self, 'current_spread', _require_number(self.current_spread, 'current_spread'))
        object.__setattr__(self, 'relative_spread', _require_number(self.relative_spread, 'relative_spread'))
        object.__setattr__(self, 'updated_utc', _require_non_empty_string(self.updated_utc, 'updated_utc'))

    @property
    def instance_key(self) -> InstanceKey:
        return InstanceKey(self.account_id, self.symbol, self.magic)

    def to_dict(self) -> dict[str, Any]:
        return {'schema_version': self.schema_version, 'account_id': self.account_id, 'symbol': self.symbol, 'magic': self.magic, 'sample_count': self.sample_count, 'mean_spread': self.mean_spread, 'std_spread': self.std_spread, 'median_spread': self.median_spread, 'current_spread': self.current_spread, 'relative_spread': self.relative_spread, 'updated_utc': self.updated_utc}

@dataclass(frozen=True)
class DecisionJournalEntry:
    decision_id: str
    timestamp_utc: str
    account_id: str
    symbol: str
    magic: int
    decision: str
    reason: str
    risk_result: str
    buy_score: float | None = None
    sell_score: float | None = None
    risk_reason: str | None = None
    ai_mode: str | None = None
    ai_available: bool | None = None
    ai_error_type: str | None = None
    ai_fallback_used: bool | None = None
    ai_reason: str | None = None
    system_decision_before_ai: str | None = None
    decision_after_ai: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'decision_id', _require_non_empty_string(self.decision_id, 'decision_id'))
        object.__setattr__(self, 'timestamp_utc', _require_non_empty_string(self.timestamp_utc, 'timestamp_utc'))
        object.__setattr__(self, 'account_id', _validate_account_id(self.account_id))
        object.__setattr__(self, 'symbol', _validate_symbol(self.symbol))
        object.__setattr__(self, 'magic', _validate_magic(self.magic))
        decision = _require_non_empty_string(self.decision, 'decision')
        if not is_valid_decision(decision):
            raise ValidationError('decision is invalid', module='protocol.models', context={'value': decision})
        object.__setattr__(self, 'decision', decision)
        object.__setattr__(self, 'reason', _require_non_empty_string(self.reason, 'reason'))
        risk_result = _require_non_empty_string(self.risk_result, 'risk_result')
        if not is_valid_risk_result(risk_result):
            raise ValidationError('risk_result is invalid', module='protocol.models', context={'value': risk_result})
        object.__setattr__(self, 'risk_result', risk_result)
        if self.buy_score is not None:
            object.__setattr__(self, 'buy_score', _require_number(self.buy_score, 'buy_score'))
        if self.sell_score is not None:
            object.__setattr__(self, 'sell_score', _require_number(self.sell_score, 'sell_score'))
        if self.risk_reason is not None:
            object.__setattr__(self, 'risk_reason', _require_non_empty_string(self.risk_reason, 'risk_reason'))
        if self.ai_mode is not None:
            object.__setattr__(self, 'ai_mode', _require_non_empty_string(self.ai_mode, 'ai_mode'))
        if self.ai_available is not None:
            object.__setattr__(self, 'ai_available', bool(self.ai_available))
        if self.ai_error_type is not None:
            object.__setattr__(self, 'ai_error_type', _require_non_empty_string(self.ai_error_type, 'ai_error_type'))
        if self.ai_fallback_used is not None:
            object.__setattr__(self, 'ai_fallback_used', bool(self.ai_fallback_used))
        if self.ai_reason is not None:
            object.__setattr__(self, 'ai_reason', _require_non_empty_string(self.ai_reason, 'ai_reason'))
        if self.system_decision_before_ai is not None:
            system_decision = _require_non_empty_string(self.system_decision_before_ai, 'system_decision_before_ai')
            if not is_valid_decision(system_decision):
                raise ValidationError('system_decision_before_ai is invalid', module='protocol.models', context={'value': system_decision})
            object.__setattr__(self, 'system_decision_before_ai', system_decision)
        if self.decision_after_ai is not None:
            decision_after_ai = _require_non_empty_string(self.decision_after_ai, 'decision_after_ai')
            if not is_valid_decision(decision_after_ai):
                raise ValidationError('decision_after_ai is invalid', module='protocol.models', context={'value': decision_after_ai})
            object.__setattr__(self, 'decision_after_ai', decision_after_ai)

    @property
    def instance_key(self) -> InstanceKey:
        return InstanceKey(self.account_id, self.symbol, self.magic)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {'decision_id': self.decision_id, 'timestamp_utc': self.timestamp_utc, 'account_id': self.account_id, 'symbol': self.symbol, 'magic': self.magic, 'decision': self.decision, 'reason': self.reason, 'risk_result': self.risk_result}
        if self.buy_score is not None:
            data['buy_score'] = self.buy_score
        if self.sell_score is not None:
            data['sell_score'] = self.sell_score
        if self.risk_reason is not None:
            data['risk_reason'] = self.risk_reason
        if self.ai_mode is not None:
            data['ai_mode'] = self.ai_mode
        if self.ai_available is not None:
            data['ai_available'] = self.ai_available
        if self.ai_error_type is not None:
            data['ai_error_type'] = self.ai_error_type
        if self.ai_fallback_used is not None:
            data['ai_fallback_used'] = self.ai_fallback_used
        if self.ai_reason is not None:
            data['ai_reason'] = self.ai_reason
        if self.system_decision_before_ai is not None:
            data['system_decision_before_ai'] = self.system_decision_before_ai
        if self.decision_after_ai is not None:
            data['decision_after_ai'] = self.decision_after_ai
        return data

@dataclass(frozen=True)
class TradeJournalEntry:
    trade_id: str
    timestamp_utc: str
    account_id: str
    symbol: str
    magic: int
    event: str
    command_id: str
    ack_status: str
    reason: str
    side: str | None = None
    volume: float | None = None
    price: float | None = None
    ticket: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'trade_id', _require_non_empty_string(self.trade_id, 'trade_id'))
        object.__setattr__(self, 'timestamp_utc', _require_non_empty_string(self.timestamp_utc, 'timestamp_utc'))
        object.__setattr__(self, 'account_id', _validate_account_id(self.account_id))
        object.__setattr__(self, 'symbol', _validate_symbol(self.symbol))
        object.__setattr__(self, 'magic', _validate_magic(self.magic))
        event = _require_non_empty_string(self.event, 'event')
        if event not in TradeEvent._value2member_map_:
            raise ValidationError('event is invalid', module='protocol.models', context={'value': event})
        object.__setattr__(self, 'event', event)
        object.__setattr__(self, 'command_id', _require_non_empty_string(self.command_id, 'command_id'))
        ack_status = _require_non_empty_string(self.ack_status, 'ack_status')
        if not is_valid_ack_status(ack_status):
            raise ValidationError('ack_status is invalid', module='protocol.models', context={'value': ack_status})
        object.__setattr__(self, 'ack_status', ack_status)
        object.__setattr__(self, 'reason', _require_non_empty_string(self.reason, 'reason'))
        if self.side is not None:
            side = _require_non_empty_string(self.side, 'side')
            if side not in {Side.BUY.value, Side.SELL.value}:
                raise ValidationError('side is invalid', module='protocol.models', context={'value': side})
            object.__setattr__(self, 'side', side)
        if self.volume is not None:
            object.__setattr__(self, 'volume', _require_number(self.volume, 'volume'))
        if self.price is not None:
            object.__setattr__(self, 'price', _require_number(self.price, 'price'))
        if self.ticket is not None:
            object.__setattr__(self, 'ticket', _require_int(self.ticket, 'ticket', minimum=0))

    @property
    def instance_key(self) -> InstanceKey:
        return InstanceKey(self.account_id, self.symbol, self.magic)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {'trade_id': self.trade_id, 'timestamp_utc': self.timestamp_utc, 'account_id': self.account_id, 'symbol': self.symbol, 'magic': self.magic, 'event': self.event, 'command_id': self.command_id, 'ack_status': self.ack_status, 'reason': self.reason}
        if self.side is not None:
            data['side'] = self.side
        if self.volume is not None:
            data['volume'] = self.volume
        if self.price is not None:
            data['price'] = self.price
        if self.ticket is not None:
            data['ticket'] = self.ticket
        return data

@dataclass(frozen=True)
class ErrorJournalEntry:
    error_id: str
    timestamp_utc: str
    account_id: str
    module: str
    error_type: str
    message: str
    symbol: str | None = None
    magic: int | None = None
    context: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'error_id', _require_non_empty_string(self.error_id, 'error_id'))
        object.__setattr__(self, 'timestamp_utc', _require_non_empty_string(self.timestamp_utc, 'timestamp_utc'))
        object.__setattr__(self, 'account_id', _validate_account_id(self.account_id))
        object.__setattr__(self, 'module', _require_non_empty_string(self.module, 'module'))
        error_type = _require_non_empty_string(self.error_type, 'error_type')
        if error_type not in ErrorType._value2member_map_:
            raise ValidationError('error_type is invalid', module='protocol.models', context={'value': error_type})
        object.__setattr__(self, 'error_type', error_type)
        object.__setattr__(self, 'message', _require_non_empty_string(self.message, 'message'))
        if self.symbol is not None:
            object.__setattr__(self, 'symbol', _validate_symbol(self.symbol))
        if self.magic is not None:
            object.__setattr__(self, 'magic', _validate_magic(self.magic))
        if self.context is not None and (not isinstance(self.context, dict)):
            raise ValidationError('context must be a dict', module='protocol.models')

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {'error_id': self.error_id, 'timestamp_utc': self.timestamp_utc, 'account_id': self.account_id, 'module': self.module, 'error_type': self.error_type, 'message': self.message}
        if self.symbol is not None:
            data['symbol'] = self.symbol
        if self.magic is not None:
            data['magic'] = self.magic
        if self.context is not None:
            data['context'] = self.context
        return data

@dataclass(frozen=True)
class MarketBar:
    time_utc: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str
    timeframe: str
    digits: int
    point: float

    def __post_init__(self) -> None:
        object.__setattr__(self, 'time_utc', _require_non_empty_string(self.time_utc, 'time_utc'))
        object.__setattr__(self, 'open', _require_number(self.open, 'open'))
        object.__setattr__(self, 'high', _require_number(self.high, 'high'))
        object.__setattr__(self, 'low', _require_number(self.low, 'low'))
        object.__setattr__(self, 'close', _require_number(self.close, 'close'))
        object.__setattr__(self, 'volume', _require_number(self.volume, 'volume'))
        object.__setattr__(self, 'symbol', _validate_symbol(self.symbol))
        timeframe = _require_non_empty_string(self.timeframe, 'timeframe')
        if timeframe != TIMEFRAME_M1:
            raise ValidationError(f'timeframe must be {TIMEFRAME_M1}', module='protocol.models', context={'value': timeframe})
        object.__setattr__(self, 'timeframe', timeframe)
        object.__setattr__(self, 'digits', _require_int(self.digits, 'digits', minimum=0))
        object.__setattr__(self, 'point', _require_number(self.point, 'point'))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class SensorReading:
    time_utc: str
    bid: float
    ask: float
    spread: float
    spread_points: float
    symbol: str
    digits: int
    point: float

    def __post_init__(self) -> None:
        object.__setattr__(self, 'time_utc', _require_non_empty_string(self.time_utc, 'time_utc'))
        object.__setattr__(self, 'bid', _require_number(self.bid, 'bid'))
        object.__setattr__(self, 'ask', _require_number(self.ask, 'ask'))
        object.__setattr__(self, 'spread', _require_number(self.spread, 'spread'))
        object.__setattr__(self, 'spread_points', _require_number(self.spread_points, 'spread_points'))
        object.__setattr__(self, 'symbol', _validate_symbol(self.symbol))
        object.__setattr__(self, 'digits', _require_int(self.digits, 'digits', minimum=0))
        object.__setattr__(self, 'point', _require_number(self.point, 'point'))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def validate_instance_key(account_id: str, symbol: str, magic: int) -> InstanceKey:
    return InstanceKey(account_id=account_id, symbol=symbol, magic=magic)
