from __future__ import annotations

import json
from pathlib import Path

from engine.validator.universe_validator import validate_universe_json


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_universe_validator_valid_universe_is_valid() -> None:
    raw_text = (FIXTURES_DIR / "universe_valid.json").read_text(encoding="utf-8")
    result = validate_universe_json(raw_text)
    assert result.is_valid
    assert result.errors == ()


def test_universe_validator_signal_field_is_invalid() -> None:
    payload = {
        "schema_version": "1.0.0",
        "timestamp_utc": "2026-07-07T06:00:00.000Z",
        "session": "LONDON",
        "market_regime": "trending",
        "news_window_active": False,
        "signal": "BUY",
    }
    result = validate_universe_json(json.dumps(payload))
    assert not result.is_valid
    assert any("forbidden field" in error for error in result.errors)


def test_universe_validator_buy_field_is_invalid() -> None:
    payload = {
        "schema_version": "1.0.0",
        "timestamp_utc": "2026-07-07T06:00:00.000Z",
        "session": "LONDON",
        "market_regime": "trending",
        "news_window_active": False,
        "buy": True,
    }
    result = validate_universe_json(json.dumps(payload))
    assert not result.is_valid
    assert any("forbidden field" in error for error in result.errors)


def test_universe_validator_market_regime_outside_allowed_set_is_invalid() -> None:
    payload = {
        "schema_version": "1.0.0",
        "timestamp_utc": "2026-07-07T06:00:00.000Z",
        "session": "LONDON",
        "market_regime": "super_trending",
        "news_window_active": False,
    }
    result = validate_universe_json(json.dumps(payload))
    assert not result.is_valid
    assert any("market_regime is invalid" in error for error in result.errors)
