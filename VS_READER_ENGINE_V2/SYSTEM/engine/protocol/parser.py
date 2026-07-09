from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any, TypeVar

from engine.protocol.constants import (
    MARKET_CSV_COLUMNS,
    SENSOR_CSV_COLUMNS,
    is_supported_config_schema_version,
    is_supported_protocol_schema_version,
    is_supported_state_schema_version,
    is_universe_forbidden_field,
)
from engine.protocol.errors import ProtocolError, ValidationError
from engine.protocol.models import (
    AckRecord,
    AIConfig,
    AnalysisConfig,
    AnalysisWeights,
    ControlCommand,
    DashboardConfig,
    DecisionJournalEntry,
    ErrorJournalEntry,
    InstanceDefinition,
    InstanceStateRecord,
    JournalConfig,
    LoggingConfig,
    MarketBar,
    PathsConfig,
    RiskConfig,
    RuntimeConfig,
    SensorReading,
    SpreadStateRecord,
    StatusRecord,
    StatusPositionSnapshot,
    SystemConfig,
    SystemSection,
    TradeJournalEntry,
    TradeManagementSettings,
    UniverseRecord,
)

PARSER_MODULE = "protocol.parser"

ModelT = TypeVar("ModelT")


def _protocol_error(message: str, **context: Any) -> ProtocolError:
    return ProtocolError(message, module=PARSER_MODULE, context=context)


def _ensure_mapping(data: dict[str, Any] | str, label: str) -> dict[str, Any]:
    if isinstance(data, str):
        return parse_json(data)
    if not isinstance(data, dict):
        raise _protocol_error(
            f"{label} must be a JSON object",
            label=label,
            value_type=type(data).__name__,
        )
    return data


def parse_json(text: str) -> dict[str, Any]:
    if not isinstance(text, str):
        raise _protocol_error(
            "JSON input must be a string",
            value_type=type(text).__name__,
        )
    stripped = text.strip()
    if not stripped:
        raise _protocol_error("JSON input is empty")
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise _protocol_error(
            "invalid JSON",
            error=str(exc),
        ) from exc
    if not isinstance(parsed, dict):
        raise _protocol_error(
            "JSON root must be an object",
            root_type=type(parsed).__name__,
        )
    return parsed


def _require_key(data: dict[str, Any], key: str, label: str) -> Any:
    if key not in data:
        raise _protocol_error(
            f"missing required field: {key}",
            label=label,
            field=key,
        )
    return data[key]


def _validate_schema_version(
    data: dict[str, Any],
    label: str,
    validator: Any,
) -> str:
    version = _require_key(data, "schema_version", label)
    if not isinstance(version, str) or not version.strip():
        raise _protocol_error(
            "schema_version must be a non-empty string",
            label=label,
            field="schema_version",
        )
    if not validator(version):
        raise _protocol_error(
            "unsupported schema_version",
            label=label,
            schema_version=version,
        )
    return version


def _build_model(model_type: type[ModelT], label: str, **kwargs: Any) -> ModelT:
    try:
        return model_type(**kwargs)
    except ValidationError as exc:
        raise _protocol_error(
            exc.message,
            label=label,
            model=model_type.__name__,
            validation_context=exc.context,
        ) from exc
    except TypeError as exc:
        raise _protocol_error(
            f"failed to construct {model_type.__name__}",
            label=label,
            error=str(exc),
        ) from exc


def _validate_csv_header(fieldnames: list[str] | None, expected: tuple[str, ...], label: str) -> None:
    if fieldnames is None:
        raise _protocol_error("CSV header is missing", label=label)
    if tuple(fieldnames) != expected:
        raise _protocol_error(
            "CSV column header mismatch",
            label=label,
            expected=list(expected),
            actual=fieldnames,
        )


def _parse_int_value(raw: str, field_name: str, label: str) -> int:
    try:
        if "." in raw:
            raise ValueError("integer required")
        return int(raw)
    except ValueError as exc:
        raise _protocol_error(
            f"invalid integer for {field_name}",
            label=label,
            field=field_name,
            value=raw,
        ) from exc


def _parse_float_value(raw: str, field_name: str, label: str) -> float:
    try:
        return float(raw)
    except ValueError as exc:
        raise _protocol_error(
            f"invalid number for {field_name}",
            label=label,
            field=field_name,
            value=raw,
        ) from exc


def parse_market_csv(text: str) -> tuple[MarketBar, ...]:
    if not isinstance(text, str):
        raise _protocol_error(
            "market CSV input must be a string",
            value_type=type(text).__name__,
        )
    stripped = text.strip()
    if not stripped:
        raise _protocol_error("market CSV input is empty", label="market")

    reader = csv.DictReader(StringIO(stripped))
    _validate_csv_header(reader.fieldnames, MARKET_CSV_COLUMNS, "market")

    bars: list[MarketBar] = []
    for row_number, row in enumerate(reader, start=2):
        if row is None:
            continue
        if not any(value not in (None, "") for value in row.values()):
            continue
        try:
            bars.append(
                _build_model(
                    MarketBar,
                    "market",
                    time_utc=row["time_utc"],
                    open=_parse_float_value(row["open"], "open", "market"),
                    high=_parse_float_value(row["high"], "high", "market"),
                    low=_parse_float_value(row["low"], "low", "market"),
                    close=_parse_float_value(row["close"], "close", "market"),
                    volume=_parse_float_value(row["volume"], "volume", "market"),
                    symbol=row["symbol"],
                    timeframe=row["timeframe"],
                    digits=_parse_int_value(row["digits"], "digits", "market"),
                    point=_parse_float_value(row["point"], "point", "market"),
                )
            )
        except ProtocolError as exc:
            raise _protocol_error(
                exc.message,
                label="market",
                row=row_number,
                validation_context=exc.context,
            ) from exc

    return tuple(bars)


def parse_sensor_csv(text: str) -> tuple[SensorReading, ...]:
    if not isinstance(text, str):
        raise _protocol_error(
            "sensor CSV input must be a string",
            value_type=type(text).__name__,
        )
    stripped = text.strip()
    if not stripped:
        raise _protocol_error("sensor CSV input is empty", label="sensor")

    reader = csv.DictReader(StringIO(stripped))
    _validate_csv_header(reader.fieldnames, SENSOR_CSV_COLUMNS, "sensor")

    readings: list[SensorReading] = []
    for row_number, row in enumerate(reader, start=2):
        if row is None:
            continue
        if not any(value not in (None, "") for value in row.values()):
            continue
        try:
            readings.append(
                _build_model(
                    SensorReading,
                    "sensor",
                    time_utc=row["time_utc"],
                    bid=_parse_float_value(row["bid"], "bid", "sensor"),
                    ask=_parse_float_value(row["ask"], "ask", "sensor"),
                    spread=_parse_float_value(row["spread"], "spread", "sensor"),
                    spread_points=_parse_float_value(
                        row["spread_points"],
                        "spread_points",
                        "sensor",
                    ),
                    symbol=row["symbol"],
                    digits=_parse_int_value(row["digits"], "digits", "sensor"),
                    point=_parse_float_value(row["point"], "point", "sensor"),
                )
            )
        except ProtocolError as exc:
            raise _protocol_error(
                exc.message,
                label="sensor",
                row=row_number,
                validation_context=exc.context,
            ) from exc

    return tuple(readings)


def _check_universe_root_fields(data: dict[str, Any]) -> None:
    for key in data:
        if is_universe_forbidden_field(key):
            raise _protocol_error(
                f"universe contains forbidden field: {key}",
                label="universe",
                field=key,
            )


def _parse_analysis_weights(analysis_data: dict[str, Any]) -> AnalysisWeights:
    weights_data = _require_key(analysis_data, "weights", "system_config")
    if not isinstance(weights_data, dict):
        raise _protocol_error(
            "analysis.weights must be an object",
            field="analysis.weights",
            value_type=type(weights_data).__name__,
        )
    return _build_model(
        AnalysisWeights,
        "system_config",
        momentum=_require_key(weights_data, "momentum", "system_config"),
        trend=_require_key(weights_data, "trend", "system_config"),
        structure=_require_key(weights_data, "structure", "system_config"),
        pressure=_require_key(weights_data, "pressure", "system_config"),
        behavior=_require_key(weights_data, "behavior", "system_config"),
        impact=_require_key(weights_data, "impact", "system_config"),
        context=_require_key(weights_data, "context", "system_config"),
    )


def parse_system_config(data: dict[str, Any] | str) -> SystemConfig:
    payload = _ensure_mapping(data, "system_config")
    schema_version = _validate_schema_version(
        payload,
        "system_config",
        is_supported_config_schema_version,
    )
    system_data = _require_key(payload, "system", "system_config")
    if not isinstance(system_data, dict):
        raise _protocol_error(
            "system section must be an object",
            label="system_config",
            field="system",
            value_type=type(system_data).__name__,
        )
    paths_data = _require_key(payload, "paths", "system_config")
    if not isinstance(paths_data, dict):
        raise _protocol_error(
            "paths section must be an object",
            label="system_config",
            field="paths",
            value_type=type(paths_data).__name__,
        )
    runtime_data = _require_key(payload, "runtime", "system_config")
    if not isinstance(runtime_data, dict):
        raise _protocol_error(
            "runtime section must be an object",
            label="system_config",
            field="runtime",
            value_type=type(runtime_data).__name__,
        )
    instances_data = _require_key(payload, "instances", "system_config")
    risk_data = _require_key(payload, "risk", "system_config")
    if not isinstance(risk_data, dict):
        raise _protocol_error(
            "risk section must be an object",
            label="system_config",
            field="risk",
            value_type=type(risk_data).__name__,
        )
    analysis_data = _require_key(payload, "analysis", "system_config")
    if not isinstance(analysis_data, dict):
        raise _protocol_error(
            "analysis section must be an object",
            label="system_config",
            field="analysis",
            value_type=type(analysis_data).__name__,
        )
    journal_data = _require_key(payload, "journal", "system_config")
    if not isinstance(journal_data, dict):
        raise _protocol_error(
            "journal section must be an object",
            label="system_config",
            field="journal",
            value_type=type(journal_data).__name__,
        )
    dashboard_data = _require_key(payload, "dashboard", "system_config")
    if not isinstance(dashboard_data, dict):
        raise _protocol_error(
            "dashboard section must be an object",
            label="system_config",
            field="dashboard",
            value_type=type(dashboard_data).__name__,
        )
    logging_data = _require_key(payload, "logging", "system_config")
    if not isinstance(logging_data, dict):
        raise _protocol_error(
            "logging section must be an object",
            label="system_config",
            field="logging",
            value_type=type(logging_data).__name__,
        )
    ai_data = _require_key(payload, "ai", "system_config")
    if not isinstance(ai_data, dict):
        raise _protocol_error(
            "ai section must be an object",
            label="system_config",
            field="ai",
            value_type=type(ai_data).__name__,
        )
    trade_management_data = _require_key(payload, "trade_management", "system_config")
    if not isinstance(trade_management_data, dict):
        raise _protocol_error(
            "trade_management section must be an object",
            label="system_config",
            field="trade_management",
            value_type=type(trade_management_data).__name__,
        )

    if not isinstance(instances_data, list):
        raise _protocol_error(
            "instances must be a list",
            label="system_config",
            value_type=type(instances_data).__name__,
        )

    instances: list[InstanceDefinition] = []
    for index, item in enumerate(instances_data):
        if not isinstance(item, dict):
            raise _protocol_error(
                "instance entry must be an object",
                label="system_config",
                index=index,
            )
        instances.append(
            _build_model(
                InstanceDefinition,
                "system_config",
                account_id=_require_key(item, "account_id", "system_config"),
                symbol=_require_key(item, "symbol", "system_config"),
                magic=_require_key(item, "magic", "system_config"),
                enabled=_require_key(item, "enabled", "system_config"),
            )
        )

    return _build_model(
        SystemConfig,
        "system_config",
        schema_version=schema_version,
        system=_build_model(
            SystemSection,
            "system_config",
            name=_require_key(system_data, "name", "system_config"),
            root_path=_require_key(system_data, "root_path", "system_config"),
            timeframe=_require_key(system_data, "timeframe", "system_config"),
        ),
        paths=_build_model(
            PathsConfig,
            "system_config",
            clients=_require_key(paths_data, "clients", "system_config"),
            logs=_require_key(paths_data, "logs", "system_config"),
            cache=_require_key(paths_data, "cache", "system_config"),
            history=_require_key(paths_data, "history", "system_config"),
            universe=_require_key(paths_data, "universe", "system_config"),
        ),
        runtime=_build_model(
            RuntimeConfig,
            "system_config",
            cycle_interval_ms=_require_key(runtime_data, "cycle_interval_ms", "system_config"),
            ack_timeout_ms=_require_key(runtime_data, "ack_timeout_ms", "system_config"),
            retry_max=_require_key(runtime_data, "retry_max", "system_config"),
            retry_delay_ms=_require_key(runtime_data, "retry_delay_ms", "system_config"),
            data_stale_threshold_ms=_require_key(
                runtime_data,
                "data_stale_threshold_ms",
                "system_config",
            ),
            cycle_max_duration_ms=_require_key(
                runtime_data,
                "cycle_max_duration_ms",
                "system_config",
            ),
            metrics_interval_ms=_require_key(runtime_data, "metrics_interval_ms", "system_config"),
            auto_discover_instances=_require_key(
                runtime_data,
                "auto_discover_instances",
                "system_config",
            ),
        ),
        instances=tuple(instances),
        risk=_build_model(
            RiskConfig,
            "system_config",
            max_open_positions_per_instance=_require_key(
                risk_data,
                "max_open_positions_per_instance",
                "system_config",
            ),
            max_daily_loss_percent=_require_key(
                risk_data,
                "max_daily_loss_percent",
                "system_config",
            ),
            max_drawdown_percent=_require_key(
                risk_data,
                "max_drawdown_percent",
                "system_config",
            ),
            reward_ratio=_require_key(risk_data, "reward_ratio", "system_config"),
            max_risk_per_trade_percent=_require_key(
                risk_data,
                "max_risk_per_trade_percent",
                "system_config",
            ),
            max_stop_loss_pips=_require_key(risk_data, "max_stop_loss_pips", "system_config"),
            volume_step=_require_key(risk_data, "volume_step", "system_config"),
        ),
        analysis=_build_model(
            AnalysisConfig,
            "system_config",
            lookback_bars=_require_key(analysis_data, "lookback_bars", "system_config"),
            spread_relative_threshold=_require_key(
                analysis_data,
                "spread_relative_threshold",
                "system_config",
            ),
            volatility_relative_threshold=_require_key(
                analysis_data,
                "volatility_relative_threshold",
                "system_config",
            ),
            block_high_impact_news=_require_key(
                analysis_data,
                "block_high_impact_news",
                "system_config",
            ),
            stop_loss_buffer=_require_key(analysis_data, "stop_loss_buffer", "system_config"),
            weights=_parse_analysis_weights(analysis_data),
        ),
        journal=_build_model(
            JournalConfig,
            "system_config",
            retention_days=_require_key(journal_data, "retention_days", "system_config"),
        ),
        trade_management=_build_model(
            TradeManagementSettings,
            "system_config",
            enabled=_require_key(trade_management_data, "enabled", "system_config"),
            breakeven_progress_ratio=_require_key(
                trade_management_data,
                "breakeven_progress_ratio",
                "system_config",
            ),
            partial_close_progress_ratio=_require_key(
                trade_management_data,
                "partial_close_progress_ratio",
                "system_config",
            ),
            partial_close_volume_ratio=_require_key(
                trade_management_data,
                "partial_close_volume_ratio",
                "system_config",
            ),
            time_stop_max_bars=_require_key(
                trade_management_data,
                "time_stop_max_bars",
                "system_config",
            ),
        ),
        dashboard=_build_model(
            DashboardConfig,
            "system_config",
            refresh_interval_ms=_require_key(
                dashboard_data,
                "refresh_interval_ms",
                "system_config",
            ),
        ),
        logging=_build_model(
            LoggingConfig,
            "system_config",
            level=_require_key(logging_data, "level", "system_config"),
            format=_require_key(logging_data, "format", "system_config"),
        ),
        ai=_build_model(
            AIConfig,
            "system_config",
            mode=_require_key(ai_data, "mode", "system_config"),
            fail_closed=_require_key(ai_data, "fail_closed", "system_config"),
            reject_action=_require_key(ai_data, "reject_action", "system_config"),
            timeout_ms=_require_key(ai_data, "timeout_ms", "system_config"),
            retry_max=_require_key(ai_data, "retry_max", "system_config"),
            retry_delay_ms=_require_key(ai_data, "retry_delay_ms", "system_config"),
        ),
    )


def _parse_status_positions(payload: dict[str, Any]) -> tuple[StatusPositionSnapshot, ...]:
    raw_positions = payload.get("open_positions")
    if raw_positions is None:
        return ()
    if not isinstance(raw_positions, list):
        raise _protocol_error(
            "open_positions must be a list",
            label="status",
            value_type=type(raw_positions).__name__,
        )
    positions: list[StatusPositionSnapshot] = []
    for index, item in enumerate(raw_positions):
        if not isinstance(item, dict):
            raise _protocol_error(
                "open_positions entry must be an object",
                label="status",
                index=index,
                value_type=type(item).__name__,
            )
        kwargs: dict[str, Any] = {
            "symbol": _require_key(item, "symbol", "status"),
            "magic": _require_key(item, "magic", "status"),
            "ticket": _require_key(item, "ticket", "status"),
            "side": _require_key(item, "side", "status"),
            "volume": _require_key(item, "volume", "status"),
        }
        if "entry_price" in item and item["entry_price"] is not None:
            kwargs["entry_price"] = item["entry_price"]
        if "stop_loss" in item and item["stop_loss"] is not None:
            kwargs["stop_loss"] = item["stop_loss"]
        if "take_profit" in item and item["take_profit"] is not None:
            kwargs["take_profit"] = item["take_profit"]
        positions.append(_build_model(StatusPositionSnapshot, "status", **kwargs))
    return tuple(positions)


def parse_status(data: dict[str, Any] | str) -> StatusRecord:
    payload = _ensure_mapping(data, "status")
    schema_version = _validate_schema_version(
        payload,
        "status",
        is_supported_protocol_schema_version,
    )
    kwargs: dict[str, Any] = {
        "schema_version": schema_version,
        "timestamp_utc": _require_key(payload, "timestamp_utc", "status"),
        "account_id": _require_key(payload, "account_id", "status"),
        "connected": _require_key(payload, "connected", "status"),
        "trade_allowed": _require_key(payload, "trade_allowed", "status"),
        "balance": _require_key(payload, "balance", "status"),
        "equity": _require_key(payload, "equity", "status"),
        "margin_free": _require_key(payload, "margin_free", "status"),
        "ea_version": _require_key(payload, "ea_version", "status"),
        "open_positions": _parse_status_positions(payload),
    }
    if "last_error" in payload and payload["last_error"] is not None:
        kwargs["last_error"] = payload["last_error"]
    return _build_model(StatusRecord, "status", **kwargs)


def parse_universe(data: dict[str, Any] | str) -> UniverseRecord:
    payload = _ensure_mapping(data, "universe")
    _check_universe_root_fields(payload)
    schema_version = _validate_schema_version(
        payload,
        "universe",
        is_supported_protocol_schema_version,
    )
    kwargs: dict[str, Any] = {
        "schema_version": schema_version,
        "timestamp_utc": _require_key(payload, "timestamp_utc", "universe"),
        "session": _require_key(payload, "session", "universe"),
        "market_regime": _require_key(payload, "market_regime", "universe"),
        "news_window_active": _require_key(payload, "news_window_active", "universe"),
    }
    if "news_impact_level" in payload and payload["news_impact_level"] is not None:
        kwargs["news_impact_level"] = payload["news_impact_level"]
    if "correlation_group" in payload and payload["correlation_group"] is not None:
        kwargs["correlation_group"] = payload["correlation_group"]
    if "metadata" in payload and payload["metadata"] is not None:
        kwargs["metadata"] = payload["metadata"]
    return _build_model(UniverseRecord, "universe", **kwargs)


def parse_control(data: dict[str, Any] | str) -> ControlCommand:
    payload = _ensure_mapping(data, "control")
    schema_version = _validate_schema_version(
        payload,
        "control",
        is_supported_protocol_schema_version,
    )
    kwargs: dict[str, Any] = {
        "schema_version": schema_version,
        "timestamp_utc": _require_key(payload, "timestamp_utc", "control"),
        "command_id": _require_key(payload, "command_id", "control"),
        "account_id": _require_key(payload, "account_id", "control"),
        "symbol": _require_key(payload, "symbol", "control"),
        "magic": _require_key(payload, "magic", "control"),
        "action": _require_key(payload, "action", "control"),
        "reason": _require_key(payload, "reason", "control"),
        "decision_id": _require_key(payload, "decision_id", "control"),
    }
    for optional in ("side", "volume", "stop_loss", "take_profit", "ticket"):
        if optional in payload and payload[optional] is not None:
            kwargs[optional] = payload[optional]
    return _build_model(ControlCommand, "control", **kwargs)


def parse_ack(data: dict[str, Any] | str) -> AckRecord:
    payload = _ensure_mapping(data, "ack")
    schema_version = _validate_schema_version(
        payload,
        "ack",
        is_supported_protocol_schema_version,
    )
    kwargs: dict[str, Any] = {
        "schema_version": schema_version,
        "timestamp_utc": _require_key(payload, "timestamp_utc", "ack"),
        "command_id": _require_key(payload, "command_id", "ack"),
        "account_id": _require_key(payload, "account_id", "ack"),
        "symbol": _require_key(payload, "symbol", "ack"),
        "magic": _require_key(payload, "magic", "ack"),
        "status": _require_key(payload, "status", "ack"),
    }
    for optional in ("ticket", "error_code", "error_message"):
        if optional in payload and payload[optional] is not None:
            kwargs[optional] = payload[optional]
    return _build_model(AckRecord, "ack", **kwargs)


def parse_instance_state(data: dict[str, Any] | str) -> InstanceStateRecord:
    payload = _ensure_mapping(data, "instance_state")
    schema_version = _validate_schema_version(
        payload,
        "instance_state",
        is_supported_state_schema_version,
    )
    kwargs: dict[str, Any] = {
        "schema_version": schema_version,
        "account_id": _require_key(payload, "account_id", "instance_state"),
        "symbol": _require_key(payload, "symbol", "instance_state"),
        "magic": _require_key(payload, "magic", "instance_state"),
        "last_decision": _require_key(payload, "last_decision", "instance_state"),
        "last_reason": _require_key(payload, "last_reason", "instance_state"),
        "last_command_id": _require_key(payload, "last_command_id", "instance_state"),
        "last_ack_status": _require_key(payload, "last_ack_status", "instance_state"),
        "instrument_digits": _require_key(payload, "instrument_digits", "instance_state"),
        "instrument_point": _require_key(payload, "instrument_point", "instance_state"),
        "instrument_pip": _require_key(payload, "instrument_pip", "instance_state"),
        "cycle_count": _require_key(payload, "cycle_count", "instance_state"),
        "last_cycle_utc": _require_key(payload, "last_cycle_utc", "instance_state"),
    }
    for optional in ("open_ticket", "position_side", "position_volume"):
        if optional in payload and payload[optional] is not None:
            kwargs[optional] = payload[optional]
    return _build_model(InstanceStateRecord, "instance_state", **kwargs)


def parse_spread_state(data: dict[str, Any] | str) -> SpreadStateRecord:
    payload = _ensure_mapping(data, "spread_state")
    schema_version = _validate_schema_version(
        payload,
        "spread_state",
        is_supported_state_schema_version,
    )
    return _build_model(
        SpreadStateRecord,
        "spread_state",
        schema_version=schema_version,
        account_id=_require_key(payload, "account_id", "spread_state"),
        symbol=_require_key(payload, "symbol", "spread_state"),
        magic=_require_key(payload, "magic", "spread_state"),
        sample_count=_require_key(payload, "sample_count", "spread_state"),
        mean_spread=_require_key(payload, "mean_spread", "spread_state"),
        std_spread=_require_key(payload, "std_spread", "spread_state"),
        median_spread=_require_key(payload, "median_spread", "spread_state"),
        current_spread=_require_key(payload, "current_spread", "spread_state"),
        relative_spread=_require_key(payload, "relative_spread", "spread_state"),
        updated_utc=_require_key(payload, "updated_utc", "spread_state"),
    )


def parse_decision_journal_line(line: str) -> DecisionJournalEntry:
    if not isinstance(line, str) or not line.strip():
        raise _protocol_error("decision journal line is empty", label="decision_journal")
    payload = parse_json(line)
    kwargs: dict[str, Any] = {
        "decision_id": _require_key(payload, "decision_id", "decision_journal"),
        "timestamp_utc": _require_key(payload, "timestamp_utc", "decision_journal"),
        "account_id": _require_key(payload, "account_id", "decision_journal"),
        "symbol": _require_key(payload, "symbol", "decision_journal"),
        "magic": _require_key(payload, "magic", "decision_journal"),
        "decision": _require_key(payload, "decision", "decision_journal"),
        "reason": _require_key(payload, "reason", "decision_journal"),
        "risk_result": _require_key(payload, "risk_result", "decision_journal"),
    }
    for optional in (
        "buy_score",
        "sell_score",
        "risk_reason",
        "ai_mode",
        "ai_available",
        "ai_error_type",
        "ai_fallback_used",
        "ai_reason",
        "system_decision_before_ai",
        "decision_after_ai",
    ):
        if optional in payload and payload[optional] is not None:
            kwargs[optional] = payload[optional]
    return _build_model(DecisionJournalEntry, "decision_journal", **kwargs)


def parse_trade_journal_line(line: str) -> TradeJournalEntry:
    if not isinstance(line, str) or not line.strip():
        raise _protocol_error("trade journal line is empty", label="trade_journal")
    payload = parse_json(line)
    kwargs: dict[str, Any] = {
        "trade_id": _require_key(payload, "trade_id", "trade_journal"),
        "timestamp_utc": _require_key(payload, "timestamp_utc", "trade_journal"),
        "account_id": _require_key(payload, "account_id", "trade_journal"),
        "symbol": _require_key(payload, "symbol", "trade_journal"),
        "magic": _require_key(payload, "magic", "trade_journal"),
        "event": _require_key(payload, "event", "trade_journal"),
        "command_id": _require_key(payload, "command_id", "trade_journal"),
        "ack_status": _require_key(payload, "ack_status", "trade_journal"),
        "reason": _require_key(payload, "reason", "trade_journal"),
    }
    for optional in ("side", "volume", "price", "ticket"):
        if optional in payload and payload[optional] is not None:
            kwargs[optional] = payload[optional]
    return _build_model(TradeJournalEntry, "trade_journal", **kwargs)


def parse_error_journal_line(line: str) -> ErrorJournalEntry:
    if not isinstance(line, str) or not line.strip():
        raise _protocol_error("error journal line is empty", label="error_journal")
    payload = parse_json(line)
    kwargs: dict[str, Any] = {
        "error_id": _require_key(payload, "error_id", "error_journal"),
        "timestamp_utc": _require_key(payload, "timestamp_utc", "error_journal"),
        "account_id": _require_key(payload, "account_id", "error_journal"),
        "module": _require_key(payload, "module", "error_journal"),
        "error_type": _require_key(payload, "error_type", "error_journal"),
        "message": _require_key(payload, "message", "error_journal"),
    }
    for optional in ("symbol", "magic", "context"):
        if optional in payload and payload[optional] is not None:
            kwargs[optional] = payload[optional]
    return _build_model(ErrorJournalEntry, "error_journal", **kwargs)
