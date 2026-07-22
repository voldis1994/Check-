"""Startup / runtime guards that keep live accounts from trading without hard stops."""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
from engine.protocol.constants import REASON_LIVE_SAFETY_BLOCK
from engine.reason import build_reason
if TYPE_CHECKING:
    from engine.protocol.models import SystemConfig
MODULE_NAME = 'risk.live_safety'

@dataclass(frozen=True)
class LiveSafetyResult:
    warnings: tuple[str, ...]
    block_entries: bool
    reason: str | None = None

def validate_live_safety(system_config: SystemConfig, *, is_live_account: bool) -> LiveSafetyResult:
    """Warn (demo) or block entries (live) when critical risk limits are disabled.

    Does not mutate risk schema. Live accounts must have both daily-loss and
    drawdown limits enabled before new OPEN entries are allowed.
    """
    warnings: list[str] = []
    risk = system_config.risk
    daily_disabled = not risk.daily_loss_limit_enabled
    drawdown_disabled = not risk.drawdown_limit_enabled
    if daily_disabled:
        warnings.append('risk.daily_loss_limit_enabled is false — daily loss protection is off')
    if drawdown_disabled:
        warnings.append('risk.drawdown_limit_enabled is false — drawdown protection is off')
    if not warnings:
        return LiveSafetyResult(warnings=(), block_entries=False, reason=None)
    if is_live_account and (daily_disabled or drawdown_disabled):
        reason = build_reason(
            REASON_LIVE_SAFETY_BLOCK,
            'live account requires daily_loss and drawdown limits enabled',
            daily_loss_limit_enabled=risk.daily_loss_limit_enabled,
            drawdown_limit_enabled=risk.drawdown_limit_enabled,
        )
        return LiveSafetyResult(warnings=tuple(warnings), block_entries=True, reason=reason)
    return LiveSafetyResult(warnings=tuple(warnings), block_entries=False, reason=None)
