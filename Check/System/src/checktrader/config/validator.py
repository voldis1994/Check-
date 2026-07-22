"""Live configuration validation."""

from __future__ import annotations

from checktrader.config.models import SystemConfig
from checktrader.domain.errors import ConfigurationError
from checktrader.observability.reason_codes import ReasonCode

_ALLOWED_TIMEFRAMES = frozenset({"M1", "M5", "M15", "M30", "H1", "H4", "D1"})


def validate_live_config(config: SystemConfig, *, require_live_accounts: bool = True) -> None:
    if config.runtime.mode == "live" and require_live_accounts:
        if not config.account.allowed_account_numbers:
            raise ConfigurationError(
                "allowed_account_numbers must be set for live mode",
                reason=ReasonCode.ACCOUNT_NOT_ALLOWED,
            )
    for label, value in (
        ("entry_timeframe", config.instrument.entry_timeframe),
        ("setup_timeframe", config.instrument.setup_timeframe),
        ("context_timeframe", config.instrument.context_timeframe),
    ):
        if value not in _ALLOWED_TIMEFRAMES:
            raise ConfigurationError(
                f"invalid {label}: {value}",
                reason=ReasonCode.DATA_INVALID,
                context={"field": label, "value": value},
            )
    if config.risk.sizing_mode == "fixed_lot":
        if config.risk.fixed_lot is None or config.risk.fixed_lot <= 0:
            raise ConfigurationError("fixed_lot must be > 0", reason=ReasonCode.INVALID_VOLUME)
    elif config.risk.sizing_mode == "risk_percent":
        if config.risk.risk_percent is None or config.risk.risk_percent <= 0:
            raise ConfigurationError("risk_percent must be > 0", reason=ReasonCode.RISK_CONFIG_INVALID)
    else:
        raise ConfigurationError(
            f"unknown sizing_mode: {config.risk.sizing_mode}",
            reason=ReasonCode.RISK_CONFIG_INVALID,
        )
    if config.trade_management.trailing_step_pips <= 0:
        raise ConfigurationError("trailing_step_pips must be > 0", reason=ReasonCode.RISK_CONFIG_INVALID)
