from __future__ import annotations
from enum import StrEnum
from typing import Final, FrozenSet
SYSTEM_NAME: Final[str] = 'SYSTEM'
DEFAULT_ROOT_PATH: Final[str] = 'C:\\Check\\System'
TIMEFRAME_M1: Final[str] = 'M1'
CONFIG_SCHEMA_VERSION: Final[str] = '1.0.0'
PROTOCOL_SCHEMA_VERSION: Final[str] = '1.0.0'
STATE_SCHEMA_VERSION: Final[str] = '1.0.0'
SUPPORTED_CONFIG_SCHEMA_VERSIONS: Final[FrozenSet[str]] = frozenset({CONFIG_SCHEMA_VERSION})
SUPPORTED_PROTOCOL_SCHEMA_VERSIONS: Final[FrozenSet[str]] = frozenset({PROTOCOL_SCHEMA_VERSION})
SUPPORTED_STATE_SCHEMA_VERSIONS: Final[FrozenSet[str]] = frozenset({STATE_SCHEMA_VERSION})

class Decision(StrEnum):
    BUY = 'BUY'
    SELL = 'SELL'
    WAIT = 'WAIT'
    BLOCK = 'BLOCK'

class RiskResult(StrEnum):
    ALLOW = 'ALLOW'
    BLOCK = 'BLOCK'

class Side(StrEnum):
    BUY = 'BUY'
    SELL = 'SELL'
    NONE = 'NONE'

class OrderAction(StrEnum):
    OPEN = 'OPEN'
    MODIFY = 'MODIFY'
    CLOSE = 'CLOSE'
    NONE = 'NONE'

class AckStatus(StrEnum):
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    REJECTED = 'REJECTED'
    TIMEOUT = 'TIMEOUT'

class TradeEvent(StrEnum):
    OPEN = 'OPEN'
    MODIFY = 'MODIFY'
    CLOSE = 'CLOSE'

class ErrorType(StrEnum):
    VALIDATION = 'VALIDATION'
    IO = 'IO'
    PROTOCOL = 'PROTOCOL'
    EXECUTION = 'EXECUTION'
    RISK = 'RISK'

class ValidationStatus(StrEnum):
    VALID = 'VALID'
    INVALID = 'INVALID'

class MomentumDirection(StrEnum):
    UP = 'UP'
    DOWN = 'DOWN'
    NEUTRAL = 'NEUTRAL'

class TrendDirection(StrEnum):
    UP = 'UP'
    DOWN = 'DOWN'
    SIDEWAYS = 'SIDEWAYS'

class StructureBias(StrEnum):
    BULLISH = 'BULLISH'
    BEARISH = 'BEARISH'
    NEUTRAL = 'NEUTRAL'

class MarketRegime(StrEnum):
    TRENDING = 'trending'
    RANGING = 'ranging'
    VOLATILE = 'volatile'
    QUIET = 'quiet'

class NewsImpactLevel(StrEnum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'

class TradeEnvironment(StrEnum):
    FAVORABLE = 'FAVORABLE'
    NEUTRAL = 'NEUTRAL'
    HOSTILE = 'HOSTILE'

class LogLevel(StrEnum):
    DEBUG = 'DEBUG'
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'

class AlertLevel(StrEnum):
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'
REASON_BOTH_DIRECTIONS_INVALID: Final[str] = 'BOTH_DIRECTIONS_INVALID'
REASON_EQUAL_SCORES: Final[str] = 'EQUAL_SCORES'
REASON_EXECUTION_NOT_POSSIBLE: Final[str] = 'EXECUTION_NOT_POSSIBLE'
REASON_RISK_MAX_DRAWDOWN: Final[str] = 'RISK_MAX_DRAWDOWN'
REASON_RISK_DAILY_LOSS: Final[str] = 'RISK_DAILY_LOSS'
REASON_RISK_MAX_POSITIONS: Final[str] = 'RISK_MAX_POSITIONS'
REASON_SPREAD_ABNORMAL: Final[str] = 'SPREAD_ABNORMAL'
REASON_VOLATILITY_ABNORMAL: Final[str] = 'VOLATILITY_ABNORMAL'
REASON_NEWS_WINDOW_ACTIVE: Final[str] = 'NEWS_WINDOW_ACTIVE'
REASON_ACCOUNT_NOT_TRADEABLE: Final[str] = 'ACCOUNT_NOT_TRADEABLE'
REASON_DATA_INVALID: Final[str] = 'DATA_INVALID'
REASON_MISSING_TAKE_PROFIT: Final[str] = 'MISSING_TAKE_PROFIT'
REASON_ACK_TIMEOUT: Final[str] = 'ACK_TIMEOUT'
REASON_CYCLE_TIMEOUT: Final[str] = 'CYCLE_TIMEOUT'
REASON_EXTERNAL_POSITION_CLOSE: Final[str] = 'EXTERNAL_POSITION_CLOSE'
REASON_EXTERNAL_PARTIAL_CLOSE: Final[str] = 'EXTERNAL_PARTIAL_CLOSE'
REASON_CLOSE_PENDING_RECONCILIATION: Final[str] = 'CLOSE_PENDING_RECONCILIATION'
REASON_INVALID_VOLUME: Final[str] = 'INVALID_VOLUME'
REASON_SCHEMA_UNSUPPORTED: Final[str] = 'SCHEMA_UNSUPPORTED'
REASON_INSTANCE_CONFLICT: Final[str] = 'INSTANCE_CONFLICT'
REASON_ENTRY_DEFERRED: Final[str] = 'ENTRY_DEFERRED'
ALL_REASON_CODES: Final[FrozenSet[str]] = frozenset({REASON_BOTH_DIRECTIONS_INVALID, REASON_EQUAL_SCORES, REASON_EXECUTION_NOT_POSSIBLE, REASON_RISK_MAX_DRAWDOWN, REASON_RISK_DAILY_LOSS, REASON_RISK_MAX_POSITIONS, REASON_SPREAD_ABNORMAL, REASON_VOLATILITY_ABNORMAL, REASON_NEWS_WINDOW_ACTIVE, REASON_ACCOUNT_NOT_TRADEABLE, REASON_DATA_INVALID, REASON_MISSING_TAKE_PROFIT, REASON_ACK_TIMEOUT, REASON_CYCLE_TIMEOUT, REASON_EXTERNAL_POSITION_CLOSE, REASON_EXTERNAL_PARTIAL_CLOSE, REASON_CLOSE_PENDING_RECONCILIATION, REASON_INVALID_VOLUME, REASON_SCHEMA_UNSUPPORTED, REASON_INSTANCE_CONFLICT, REASON_ENTRY_DEFERRED})
WAIT_REASON_CODES: Final[FrozenSet[str]] = frozenset({REASON_BOTH_DIRECTIONS_INVALID, REASON_EQUAL_SCORES, REASON_EXECUTION_NOT_POSSIBLE})
BLOCK_REASON_CODES: Final[FrozenSet[str]] = frozenset({REASON_RISK_MAX_DRAWDOWN, REASON_RISK_DAILY_LOSS, REASON_RISK_MAX_POSITIONS, REASON_SPREAD_ABNORMAL, REASON_VOLATILITY_ABNORMAL, REASON_NEWS_WINDOW_ACTIVE, REASON_ACCOUNT_NOT_TRADEABLE, REASON_DATA_INVALID, REASON_MISSING_TAKE_PROFIT, REASON_INVALID_VOLUME, REASON_SCHEMA_UNSUPPORTED, REASON_INSTANCE_CONFLICT, REASON_ENTRY_DEFERRED})
FILE_EXT_JSON: Final[str] = '.json'
FILE_EXT_CSV: Final[str] = '.csv'
FILE_EXT_JSONL: Final[str] = '.jsonl'
FILE_EXT_LOG: Final[str] = '.log'
FILE_EXT_TMP: Final[str] = '.tmp'
FILENAME_MARKET: Final[str] = 'market_{symbol}_{magic}.csv'
FILENAME_SENSOR: Final[str] = 'sensor_{symbol}_{magic}.csv'
FILENAME_CONTROL: Final[str] = 'control_{symbol}_{magic}.json'
FILENAME_ACK: Final[str] = 'ack_{symbol}_{magic}.json'
FILENAME_STATUS: Final[str] = 'status_{account_id}.json'
FILENAME_DECISION_JOURNAL: Final[str] = 'decision_{symbol}_{magic}.jsonl'
FILENAME_TRADE_JOURNAL: Final[str] = 'trade_{symbol}_{magic}.jsonl'
FILENAME_ERROR_JOURNAL: Final[str] = 'error_{symbol}_{magic}.jsonl'
FILENAME_INSTANCE_STATE: Final[str] = 'instance_{symbol}_{magic}.json'
FILENAME_SPREAD_STATE: Final[str] = 'spread_{symbol}_{magic}.json'
FILENAME_MONITORING_SNAPSHOT: Final[str] = 'monitoring_{symbol}_{magic}.json'
FILENAME_UNIVERSE: Final[str] = 'universe.json'
MARKET_CSV_COLUMNS: Final[tuple[str, ...]] = ('time_utc', 'open', 'high', 'low', 'close', 'volume', 'symbol', 'timeframe', 'digits', 'point')
SENSOR_CSV_COLUMNS: Final[tuple[str, ...]] = ('time_utc', 'bid', 'ask', 'spread', 'spread_points', 'symbol', 'digits', 'point')
UNIVERSE_FORBIDDEN_FIELDS: Final[FrozenSet[str]] = frozenset({'signal', 'direction', 'trade', 'buy', 'sell', 'action'})
FLOAT_TOLERANCE: Final[float] = 1e-09

def is_supported_config_schema_version(version: str) -> bool:
    return version in SUPPORTED_CONFIG_SCHEMA_VERSIONS

def is_supported_protocol_schema_version(version: str) -> bool:
    return version in SUPPORTED_PROTOCOL_SCHEMA_VERSIONS

def is_supported_state_schema_version(version: str) -> bool:
    return version in SUPPORTED_STATE_SCHEMA_VERSIONS

def is_valid_decision(value: str) -> bool:
    return value in Decision._value2member_map_

def is_valid_risk_result(value: str) -> bool:
    return value in RiskResult._value2member_map_

def is_valid_order_action(value: str) -> bool:
    return value in OrderAction._value2member_map_

def is_valid_ack_status(value: str) -> bool:
    return value in {AckStatus.SUCCESS.value, AckStatus.FAILED.value, AckStatus.REJECTED.value}

def is_valid_reason_code(value: str) -> bool:
    return value in ALL_REASON_CODES

def is_wait_reason_code(value: str) -> bool:
    return value in WAIT_REASON_CODES

def is_block_reason_code(value: str) -> bool:
    return value in BLOCK_REASON_CODES

def is_universe_forbidden_field(field_name: str) -> bool:
    return field_name in UNIVERSE_FORBIDDEN_FIELDS
