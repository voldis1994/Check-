"""Configuration loader."""

from __future__ import annotations

import json
from pathlib import Path

from checktrader.config.models import SystemConfig
from checktrader.config.validator import validate_live_config
from checktrader.domain.errors import ConfigurationError
from checktrader.observability.reason_codes import ReasonCode


def load_system_config(path: str | Path, *, require_live_accounts: bool = True) -> SystemConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigurationError(
            f"config file missing: {config_path}",
            reason=ReasonCode.DATA_MISSING,
            context={"path": str(config_path)},
        )
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    config = SystemConfig.model_validate(payload)
    validate_live_config(config, require_live_accounts=require_live_accounts)
    return config
