from __future__ import annotations

from checktrader.config.models import SystemConfig
from checktrader.domain.errors import ConfigurationError


def validate_live_ready(config: SystemConfig) -> None:
    """Strict gate for armed live trading (dashboard Start Live / validate_config --live)."""
    if config.runtime.mode != "live" or not config.runtime.trading_enabled:
        raise ConfigurationError("live execution requires runtime.mode='live' and runtime.trading_enabled=true")


def validate_runtime_safety(config: SystemConfig) -> None:
    """
    Bootstrap safety.

    Live mode without trading_enabled is allowed for bridge soak / observe.
    Orders remain blocked in risk.validator until trading_enabled=true.
    """
    if config.runtime.mode == "live" and config.runtime.trading_enabled is False:
        return
    if config.runtime.mode == "live":
        validate_live_ready(config)
