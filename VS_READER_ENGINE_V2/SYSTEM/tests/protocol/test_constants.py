from __future__ import annotations

import pytest

from engine.protocol import constants
from engine.protocol.constants import (
    AckStatus,
    AlertLevel,
    ALL_REASON_CODES,
    BLOCK_REASON_CODES,
    CONFIG_SCHEMA_VERSION,
    Decision,
    ErrorType,
    FILE_EXT_CSV,
    FILE_EXT_JSON,
    FILE_EXT_JSONL,
    FILE_EXT_LOG,
    FILE_EXT_TMP,
    FILENAME_ACK,
    FILENAME_CONTROL,
    FILENAME_DECISION_JOURNAL,
    FILENAME_ERROR_JOURNAL,
    FILENAME_INSTANCE_STATE,
    FILENAME_MARKET,
    FILENAME_SENSOR,
    FILENAME_SPREAD_STATE,
    FILENAME_STATUS,
    FILENAME_TRADE_JOURNAL,
    FILENAME_UNIVERSE,
    FLOAT_TOLERANCE,
    LogLevel,
    MARKET_CSV_COLUMNS,
    MarketRegime,
    MomentumDirection,
    NewsImpactLevel,
    OrderAction,
    PROTOCOL_SCHEMA_VERSION,
    REASON_ACCOUNT_NOT_TRADEABLE,
    REASON_ACK_TIMEOUT,
    REASON_BOTH_DIRECTIONS_INVALID,
    REASON_CYCLE_TIMEOUT,
    REASON_DATA_INVALID,
    REASON_EQUAL_SCORES,
    REASON_EXECUTION_NOT_POSSIBLE,
    REASON_MISSING_TAKE_PROFIT,
    REASON_NEWS_WINDOW_ACTIVE,
    REASON_RISK_DAILY_LOSS,
    REASON_RISK_MAX_DRAWDOWN,
    REASON_RISK_MAX_POSITIONS,
    REASON_SPREAD_ABNORMAL,
    REASON_VOLATILITY_ABNORMAL,
    RiskResult,
    SENSOR_CSV_COLUMNS,
    Side,
    STATE_SCHEMA_VERSION,
    StructureBias,
    SUPPORTED_CONFIG_SCHEMA_VERSIONS,
    SUPPORTED_PROTOCOL_SCHEMA_VERSIONS,
    SUPPORTED_STATE_SCHEMA_VERSIONS,
    SYSTEM_NAME,
    DEFAULT_ROOT_PATH,
    TIMEFRAME_M1,
    TradeEnvironment,
    TradeEvent,
    TrendDirection,
    UNIVERSE_FORBIDDEN_FIELDS,
    ValidationStatus,
    WAIT_REASON_CODES,
    is_block_reason_code,
    is_supported_config_schema_version,
    is_supported_protocol_schema_version,
    is_supported_state_schema_version,
    is_universe_forbidden_field,
    is_valid_ack_status,
    is_valid_decision,
    is_valid_order_action,
    is_valid_reason_code,
    is_valid_risk_result,
    is_wait_reason_code,
)


def test_system_identity_constants() -> None:
    assert SYSTEM_NAME == "SYSTEM"
    assert DEFAULT_ROOT_PATH == r"C:\SYSTEM"
    assert TIMEFRAME_M1 == "M1"


def test_schema_versions() -> None:
    assert CONFIG_SCHEMA_VERSION == "1.0.0"
    assert PROTOCOL_SCHEMA_VERSION == "1.0.0"
    assert STATE_SCHEMA_VERSION == "1.0.0"
    assert is_supported_config_schema_version(CONFIG_SCHEMA_VERSION)
    assert is_supported_protocol_schema_version(PROTOCOL_SCHEMA_VERSION)
    assert is_supported_state_schema_version(STATE_SCHEMA_VERSION)
    assert not is_supported_protocol_schema_version("0.0.1")


def test_supported_schema_version_sets() -> None:
    assert CONFIG_SCHEMA_VERSION in SUPPORTED_CONFIG_SCHEMA_VERSIONS
    assert PROTOCOL_SCHEMA_VERSION in SUPPORTED_PROTOCOL_SCHEMA_VERSIONS
    assert STATE_SCHEMA_VERSION in SUPPORTED_STATE_SCHEMA_VERSIONS


def test_decision_enum() -> None:
    assert Decision.BUY.value == "BUY"
    assert Decision.SELL.value == "SELL"
    assert Decision.WAIT.value == "WAIT"
    assert Decision.BLOCK.value == "BLOCK"
    assert is_valid_decision("BUY")
    assert not is_valid_decision("HOLD")


def test_risk_result_enum() -> None:
    assert RiskResult.ALLOW.value == "ALLOW"
    assert RiskResult.BLOCK.value == "BLOCK"
    assert is_valid_risk_result("ALLOW")
    assert not is_valid_risk_result("WAIT")


def test_side_enum() -> None:
    assert Side.BUY.value == "BUY"
    assert Side.SELL.value == "SELL"
    assert Side.NONE.value == "NONE"


def test_order_action_enum() -> None:
    assert OrderAction.OPEN.value == "OPEN"
    assert OrderAction.MODIFY.value == "MODIFY"
    assert OrderAction.CLOSE.value == "CLOSE"
    assert OrderAction.NONE.value == "NONE"
    assert is_valid_order_action("OPEN")
    assert not is_valid_order_action("HOLD")


def test_ack_status_enum() -> None:
    assert AckStatus.SUCCESS.value == "SUCCESS"
    assert AckStatus.FAILED.value == "FAILED"
    assert AckStatus.REJECTED.value == "REJECTED"
    assert AckStatus.TIMEOUT.value == "TIMEOUT"
    assert is_valid_ack_status("SUCCESS")
    assert is_valid_ack_status("FAILED")
    assert is_valid_ack_status("REJECTED")
    assert not is_valid_ack_status("TIMEOUT")
    assert not is_valid_ack_status("PENDING")


def test_trade_event_enum() -> None:
    assert TradeEvent.OPEN.value == "OPEN"
    assert TradeEvent.MODIFY.value == "MODIFY"
    assert TradeEvent.CLOSE.value == "CLOSE"


def test_error_type_enum() -> None:
    assert ErrorType.VALIDATION.value == "VALIDATION"
    assert ErrorType.IO.value == "IO"
    assert ErrorType.PROTOCOL.value == "PROTOCOL"
    assert ErrorType.EXECUTION.value == "EXECUTION"
    assert ErrorType.RISK.value == "RISK"


def test_validation_status_enum() -> None:
    assert ValidationStatus.VALID.value == "VALID"
    assert ValidationStatus.INVALID.value == "INVALID"


def test_analysis_enums() -> None:
    assert MomentumDirection.UP.value == "UP"
    assert MomentumDirection.DOWN.value == "DOWN"
    assert MomentumDirection.NEUTRAL.value == "NEUTRAL"
    assert TrendDirection.SIDEWAYS.value == "SIDEWAYS"
    assert StructureBias.BULLISH.value == "BULLISH"
    assert StructureBias.BEARISH.value == "BEARISH"
    assert StructureBias.NEUTRAL.value == "NEUTRAL"
    assert MarketRegime.TRENDING.value == "trending"
    assert MarketRegime.RANGING.value == "ranging"
    assert MarketRegime.VOLATILE.value == "volatile"
    assert MarketRegime.QUIET.value == "quiet"
    assert NewsImpactLevel.HIGH.value == "high"
    assert TradeEnvironment.HOSTILE.value == "HOSTILE"


def test_logging_and_alert_levels() -> None:
    assert LogLevel.DEBUG.value == "DEBUG"
    assert LogLevel.CRITICAL.value == "CRITICAL"
    assert AlertLevel.INFO.value == "INFO"
    assert AlertLevel.CRITICAL.value == "CRITICAL"


def test_reason_codes_exist_and_classified() -> None:
    expected_wait = {
        REASON_BOTH_DIRECTIONS_INVALID,
        REASON_EQUAL_SCORES,
        REASON_EXECUTION_NOT_POSSIBLE,
    }
    expected_block = {
        REASON_RISK_MAX_DRAWDOWN,
        REASON_RISK_DAILY_LOSS,
        REASON_RISK_MAX_POSITIONS,
        REASON_SPREAD_ABNORMAL,
        REASON_VOLATILITY_ABNORMAL,
        REASON_NEWS_WINDOW_ACTIVE,
        REASON_ACCOUNT_NOT_TRADEABLE,
        REASON_DATA_INVALID,
        REASON_MISSING_TAKE_PROFIT,
    }
    assert expected_wait == WAIT_REASON_CODES
    assert expected_block.issubset(BLOCK_REASON_CODES)
    assert expected_wait.issubset(ALL_REASON_CODES)
    assert REASON_ACK_TIMEOUT in ALL_REASON_CODES
    assert REASON_CYCLE_TIMEOUT in ALL_REASON_CODES
    for code in ALL_REASON_CODES:
        assert is_valid_reason_code(code)


def test_reason_code_helpers() -> None:
    assert is_wait_reason_code(REASON_EQUAL_SCORES)
    assert not is_wait_reason_code(REASON_DATA_INVALID)
    assert is_block_reason_code(REASON_DATA_INVALID)
    assert not is_block_reason_code(REASON_EQUAL_SCORES)


def test_file_extensions() -> None:
    assert FILE_EXT_JSON == ".json"
    assert FILE_EXT_CSV == ".csv"
    assert FILE_EXT_JSONL == ".jsonl"
    assert FILE_EXT_LOG == ".log"
    assert FILE_EXT_TMP == ".tmp"


def test_filename_templates() -> None:
    assert FILENAME_MARKET == "market_{symbol}_{magic}.csv"
    assert FILENAME_SENSOR == "sensor_{symbol}_{magic}.csv"
    assert FILENAME_CONTROL == "control_{symbol}_{magic}.json"
    assert FILENAME_ACK == "ack_{symbol}_{magic}.json"
    assert FILENAME_STATUS == "status_{account_id}.json"
    assert FILENAME_DECISION_JOURNAL == "decision_{symbol}_{magic}.jsonl"
    assert FILENAME_TRADE_JOURNAL == "trade_{symbol}_{magic}.jsonl"
    assert FILENAME_ERROR_JOURNAL == "error_{symbol}_{magic}.jsonl"
    assert FILENAME_INSTANCE_STATE == "instance_{symbol}_{magic}.json"
    assert FILENAME_SPREAD_STATE == "spread_{symbol}_{magic}.json"
    assert FILENAME_UNIVERSE == "universe.json"


def test_market_csv_columns() -> None:
    assert MARKET_CSV_COLUMNS == (
        "time_utc",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "symbol",
        "timeframe",
        "digits",
        "point",
    )


def test_sensor_csv_columns() -> None:
    assert SENSOR_CSV_COLUMNS == (
        "time_utc",
        "bid",
        "ask",
        "spread",
        "spread_points",
        "symbol",
        "digits",
        "point",
    )


def test_universe_forbidden_fields() -> None:
    assert UNIVERSE_FORBIDDEN_FIELDS == frozenset(
        {"signal", "direction", "trade", "buy", "sell", "action"}
    )
    assert is_universe_forbidden_field("signal")
    assert not is_universe_forbidden_field("session")


def test_float_tolerance() -> None:
    assert FLOAT_TOLERANCE > 0
    assert FLOAT_TOLERANCE < 1e-6


def test_constants_module_exports_helpers() -> None:
    assert callable(constants.is_valid_decision)
    assert callable(constants.is_supported_protocol_schema_version)
