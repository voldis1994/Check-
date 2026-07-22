from __future__ import annotations
from checktrader.config.models import SystemConfig
from checktrader.domain.errors import ConfigurationError

def validate_live_ready(config: SystemConfig) -> None:
    if config.runtime.mode != 'live' or not config.runtime.trading_enabled:
        raise ConfigurationError("live execution requires runtime.mode='live' and runtime.trading_enabled=true")
def validate_runtime_safety(config: SystemConfig) -> None:
    if config.runtime.mode == 'live': validate_live_ready(config)
