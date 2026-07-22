"""Live configuration validation."""

from __future__ import annotations

from checktrader.config.models import SystemConfig
from checktrader.domain.errors import ConfigurationError
from checktrader.observability.reason_codes import ReasonCode

_ALLOWED_TF = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}


def validate_live_config(config: SystemConfig, *, require_live_accounts: bool = True) -> None:
    if require_live_accounts and config.runtime.mode == "live" and not config.account.allowed_account_numbers:
        raise ConfigurationError(
            "allowed_account_numbers must not be empty in live mode",
            reason=ReasonCode.ACCOUNT_NOT_ALLOWED,
        )
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
    for name, tf in (
        ("entry", config.instrument.entry_timeframe),
        ("setup", config.instrument.setup_timeframe),
        ("context", config.instrument.context_timeframe),
    ):
        if tf not in _ALLOWED_TF:
            raise ConfigurationError(f"invalid {name} timeframe: {tf}", reason=ReasonCode.DATA_INVALID)
