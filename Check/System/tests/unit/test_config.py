"""Config and schema validation."""

from __future__ import annotations

import pytest

from checktrader.config.loader import load_config
from checktrader.config.validation import validate_runtime_safety
from checktrader.domain.errors import ConfigurationError


def test_example_config_loads() -> None:
    cfg = load_config()
    assert cfg.version == "3.0.0"
    assert cfg.runtime.mode == "paper"
    assert cfg.runtime.trading_enabled is False
    assert cfg.instrument.symbol == "AUTO"
    assert cfg.position_sizing.fixed_lot == 0.02
    assert cfg.position.default_lot == 0.02
    assert cfg.strategies.force_stop_atr == 0.18
    assert cfg.risk.max_stop_atr == 1.50


def test_live_observe_allowed_without_trading_enabled() -> None:
    from checktrader.config.validation import validate_live_ready

    cfg = load_config()
    live = cfg.model_copy(update={"runtime": cfg.runtime.model_copy(update={"mode": "live", "trading_enabled": False})})
    validate_runtime_safety(live)  # soak / observe OK
    with pytest.raises(ConfigurationError):
        validate_live_ready(live)  # armed live still requires trading_enabled
