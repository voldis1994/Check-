from __future__ import annotations

import json
from pathlib import Path

from engine.validator.status_validator import validate_status_json


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_status_validator_valid_status_is_valid() -> None:
    raw_text = (FIXTURES_DIR / "status_valid.json").read_text(encoding="utf-8")
    result = validate_status_json(raw_text)
    assert result.is_valid
    assert result.is_tradeable
    assert result.errors == ()


def test_status_validator_connected_false_is_valid_but_not_tradeable() -> None:
    payload = {
        "schema_version": "1.0.0",
        "timestamp_utc": "2026-07-07T06:00:00.000Z",
        "account_id": "12345",
        "connected": False,
        "trade_allowed": True,
        "balance": 10000.0,
        "equity": 10020.5,
        "margin_free": 9800.0,
        "ea_version": "1.0.0",
    }
    result = validate_status_json(json.dumps(payload))
    assert result.is_valid
    assert not result.is_tradeable


def test_status_validator_missing_balance_is_invalid() -> None:
    payload = {
        "schema_version": "1.0.0",
        "timestamp_utc": "2026-07-07T06:00:00.000Z",
        "account_id": "12345",
        "connected": True,
        "trade_allowed": True,
        "equity": 10020.5,
        "margin_free": 9800.0,
        "ea_version": "1.0.0",
    }
    result = validate_status_json(json.dumps(payload))
    assert not result.is_valid
    assert any("missing required field: balance" in error for error in result.errors)


def test_status_validator_nan_values_are_invalid() -> None:
    payload = {
        "schema_version": "1.0.0",
        "timestamp_utc": "2026-07-07T06:00:00.000Z",
        "account_id": "12345",
        "connected": True,
        "trade_allowed": True,
        "balance": float("nan"),
        "equity": float("nan"),
        "margin_free": 9800.0,
        "ea_version": "1.0.0",
    }
    result = validate_status_json(json.dumps(payload))
    assert not result.is_valid
    assert "balance must not be NaN" in result.errors
    assert "equity must not be NaN" in result.errors
