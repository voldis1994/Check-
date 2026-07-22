"""Live configuration validation."""

from __future__ import annotations

from checktrader.application.account_resolve import is_auto_account_list
from checktrader.config.models import SystemConfig
from checktrader.domain.errors import ConfigurationError
from checktrader.observability.reason_codes import ReasonCode

_ALLOWED_TF = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}


def validate_live_config(config: SystemConfig, *, require_live_accounts: bool = True) -> None:
    # Empty / AUTO allow-list means trust MT4 status account — not a config error.
    _ = require_live_accounts  # kept for API compatibility with callers
    if config.runtime.timezone.upper() != "UTC":
        raise ConfigurationError("timezone must be UTC", reason=ReasonCode.DATA_INVALID)
    if config.position_sizing.mode != "fixed_lot":
        raise ConfigurationError("only fixed_lot sizing is supported", reason=ReasonCode.RISK_CONFIG_INVALID)
    if config.position_sizing.fixed_lot <= 0:
        raise ConfigurationError("fixed_lot must be > 0", reason=ReasonCode.INVALID_VOLUME)
    if config.position_sizing.allow_broker_lot_normalization:
        raise ConfigurationError(
            "broker lot normalization is not allowed",
            reason=ReasonCode.RISK_CONFIG_INVALID,
        )
    if config.trade_management.be_activation_r is not None:
        raise ConfigurationError("be_activation_r must be null", reason=ReasonCode.RISK_CONFIG_INVALID)
    if not is_auto_account_list(config.account.allowed_account_numbers):
        for item in config.account.allowed_account_numbers:
            if not str(item).strip():
                raise ConfigurationError("empty account number in allow-list", reason=ReasonCode.ACCOUNT_NOT_ALLOWED)
    for name, tf in (
        ("entry", config.instrument.entry_timeframe),
        ("setup", config.instrument.setup_timeframe),
        ("context", config.instrument.context_timeframe),
    ):
        if tf not in _ALLOWED_TF:
            raise ConfigurationError(f"invalid {name} timeframe: {tf}", reason=ReasonCode.DATA_INVALID)
