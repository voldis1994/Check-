from __future__ import annotations

import json

import pytest

from engine.protocol.constants import PROTOCOL_SCHEMA_VERSION, UNIVERSE_FORBIDDEN_FIELDS
from engine.protocol.writer import UNIVERSE_REQUIRED_FIELDS
from engine.validator.universe_validator import validate_universe_json
from tests.mql4 import mql_source, status_reference, universe_reference


@pytest.fixture
def universe_source() -> str:
    return mql_source.load_mqh("SYSTEM_Universe.mqh")


def test_system_universe_public_functions_are_defined(universe_source: str) -> None:
    expected = {
        "SYSTEM_IsUniverseForbiddenField",
        "SYSTEM_BuildUniverseFilePath",
        "SYSTEM_DetectTradingSession",
        "SYSTEM_DetectMarketRegime",
        "SYSTEM_BuildUniverseJson",
        "SYSTEM_BuildUniverseJsonFromContext",
        "SYSTEM_ExportUniverse",
        "SYSTEM_UniversePerformsAnalysis",
    }
    assert expected.issubset(set(mql_source.public_function_names(universe_source)))


def test_system_is_universe_forbidden_field_matches_protocol_set() -> None:
    for field in UNIVERSE_FORBIDDEN_FIELDS:
        assert universe_reference.is_universe_forbidden_field(field)
    assert not universe_reference.is_universe_forbidden_field("session")


def test_system_is_universe_forbidden_field_function_checks_trade_signal_fields(universe_source: str) -> None:
    body = mql_source.function_body(universe_source, "SYSTEM_IsUniverseForbiddenField")
    for field in ("signal", "direction", "trade", "buy", "sell", "action"):
        assert f'"{field}"' in body


def test_system_build_universe_file_path_uses_account_universe_filename() -> None:
    path = status_reference.build_universe_file_path(r"C:\SYSTEM", "12345")
    assert path == r"C:\SYSTEM\data\clients\12345\universe.json"


def test_system_build_universe_file_path_function_uses_universe_filename(universe_source: str) -> None:
    body = mql_source.function_body(universe_source, "SYSTEM_BuildUniverseFilePath")
    assert "SYSTEM_UNIVERSE_FILENAME" in body
    assert "SYSTEM_BuildAccountDir" in body


def test_system_detect_trading_session_maps_utc_hours() -> None:
    assert status_reference.detect_trading_session(6) == "ASIA"
    assert status_reference.detect_trading_session(10) == "LONDON"
    assert status_reference.detect_trading_session(15) == "NEW_YORK"
    assert status_reference.detect_trading_session(23) == "OFF"


def test_system_detect_trading_session_function_uses_time_gmt(universe_source: str) -> None:
    body = mql_source.function_body(universe_source, "SYSTEM_DetectTradingSession")
    assert "TimeGMT" in body
    assert "SYSTEM_SESSION_LONDON" in body


def test_system_detect_market_regime_returns_allowed_regime() -> None:
    assert status_reference.detect_market_regime() == "ranging"


def test_system_detect_market_regime_function_returns_allowed_value(universe_source: str) -> None:
    body = mql_source.function_body(universe_source, "SYSTEM_DetectMarketRegime")
    assert "SYSTEM_REGIME_RANGING" in body


def test_system_build_universe_json_contains_required_fields_and_schema_version() -> None:
    payload_text = status_reference.build_universe_json(
        session="LONDON",
        market_regime="trending",
        news_window_active=False,
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )
    payload = json.loads(payload_text)
    for field in UNIVERSE_REQUIRED_FIELDS:
        assert field in payload
    assert payload["schema_version"] == PROTOCOL_SCHEMA_VERSION
    assert validate_universe_json(payload_text).is_valid


def test_system_build_universe_json_does_not_contain_trade_signal_fields() -> None:
    payload_text = status_reference.build_universe_json(
        session="LONDON",
        market_regime="trending",
        news_window_active=False,
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )
    assert universe_reference.universe_json_contains_forbidden_fields(payload_text) == []


def test_system_build_universe_json_function_excludes_forbidden_trade_signal_fields(universe_source: str) -> None:
    body = mql_source.function_body(universe_source, "SYSTEM_BuildUniverseJson")
    for field in UNIVERSE_FORBIDDEN_FIELDS:
        assert f'"{field}"' not in body


def test_system_build_universe_json_from_context_uses_detectors(universe_source: str) -> None:
    body = mql_source.function_body(universe_source, "SYSTEM_BuildUniverseJsonFromContext")
    assert "SYSTEM_DetectTradingSession" in body
    assert "SYSTEM_DetectMarketRegime" in body


def test_system_export_universe_uses_atomic_write(universe_source: str) -> None:
    body = mql_source.function_body(universe_source, "SYSTEM_ExportUniverse")
    assert "SYSTEM_AtomicWriteText" in body
    assert "SYSTEM_BuildUniverseJsonFromContext" in body


def test_system_universe_performs_analysis_returns_false(universe_source: str) -> None:
    body = mql_source.function_body(universe_source, "SYSTEM_UniversePerformsAnalysis")
    assert "false" in body.lower()
