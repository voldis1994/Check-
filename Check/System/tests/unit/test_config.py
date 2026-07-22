"""Config loader / validator tests (SYSTEM v2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from checktrader.config.loader import load_system_config
from checktrader.config.models import SystemConfig
from checktrader.config.validator import validate_live_config
from checktrader.domain.errors import ConfigurationError
from checktrader.observability.reason_codes import ReasonCode
from tests.fixtures.helpers import SYSTEM_TEST_CONFIG, load_test_config


def test_valid_system_test_config_loads() -> None:
    config = load_system_config(SYSTEM_TEST_CONFIG)
    assert config.version == "2.0.0"
    assert config.account.allowed_account_numbers == ["999"]
    assert config.instrument.symbol == "EURUSD"
    assert config.trade_management.trailing_step_pips == 3.0


def test_empty_allowed_accounts_fails_live(tmp_path: Path) -> None:
    payload = json.loads(SYSTEM_TEST_CONFIG.read_text(encoding="utf-8"))
    payload["account"]["allowed_account_numbers"] = []
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ConfigurationError) as exc:
        load_system_config(path, require_live_accounts=True)
    assert exc.value.reason is ReasonCode.ACCOUNT_NOT_ALLOWED


def test_empty_allowed_accounts_ok_when_not_required() -> None:
    config = SystemConfig.model_validate(json.loads(SYSTEM_TEST_CONFIG.read_text(encoding="utf-8")))
    config.account.allowed_account_numbers = []
    validate_live_config(config, require_live_accounts=False)


def test_bad_exit_pressure_weights() -> None:
    payload = json.loads(SYSTEM_TEST_CONFIG.read_text(encoding="utf-8"))
    payload["trade_management"]["exit_pressure"]["pullback_weight"] = 0.9
    with pytest.raises(PydanticValidationError):
        SystemConfig.model_validate(payload)


def test_negative_trailing_step_rejected() -> None:
    payload = json.loads(SYSTEM_TEST_CONFIG.read_text(encoding="utf-8"))
    payload["trade_management"]["trailing_step_pips"] = -1.0
    with pytest.raises(PydanticValidationError):
        SystemConfig.model_validate(payload)


def test_invalid_fixed_lot_rejected(tmp_path: Path) -> None:
    payload = json.loads(SYSTEM_TEST_CONFIG.read_text(encoding="utf-8"))
    payload["risk"]["fixed_lot"] = 0.0
    path = tmp_path / "lot.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ConfigurationError) as exc:
        load_system_config(path)
    assert exc.value.reason is ReasonCode.INVALID_VOLUME


def test_bad_timeframe_rejected(tmp_path: Path) -> None:
    payload = json.loads(SYSTEM_TEST_CONFIG.read_text(encoding="utf-8"))
    payload["instrument"]["entry_timeframe"] = "M7"
    path = tmp_path / "tf.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ConfigurationError) as exc:
        load_system_config(path)
    assert exc.value.reason is ReasonCode.DATA_INVALID


def test_load_test_config_helper_override() -> None:
    config = load_test_config(risk={"fixed_lot": 0.05})
    assert config.risk.fixed_lot == 0.05
