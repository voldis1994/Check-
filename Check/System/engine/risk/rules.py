from __future__ import annotations
from dataclasses import dataclass
from engine.reason import build_reason
from engine.protocol.constants import REASON_ACCOUNT_NOT_TRADEABLE, REASON_RISK_DAILY_LOSS, REASON_RISK_MAX_DRAWDOWN, REASON_RISK_MAX_POSITIONS
from engine.protocol.models import RiskConfig, StatusRecord
from engine.state.instance_state import InstanceState

@dataclass(frozen=True)
class RiskContext:
    daily_loss_percent: float
    drawdown_percent: float

@dataclass(frozen=True)
class RiskRuleResult:
    allowed: bool
    reason: str | None

def _allowed() -> RiskRuleResult:
    return RiskRuleResult(allowed=True, reason=None)

def _blocked(reason: str) -> RiskRuleResult:
    return RiskRuleResult(allowed=False, reason=reason)

def open_position_count(instance_state: InstanceState) -> int:
    return 1 if instance_state.open_ticket is not None else 0

def check_trade_allowed(*, status: StatusRecord) -> RiskRuleResult:
    if status.trade_allowed:
        return _allowed()
    return _blocked(build_reason(REASON_ACCOUNT_NOT_TRADEABLE, 'account trading is disabled', account_id=status.account_id))

def check_max_open_positions(*, instance_state: InstanceState, risk_config: RiskConfig) -> RiskRuleResult:
    current_count = open_position_count(instance_state)
    if current_count < risk_config.max_open_positions_per_instance:
        return _allowed()
    return _blocked(build_reason(REASON_RISK_MAX_POSITIONS, 'open position limit reached', open_position_count=current_count, max_open_positions_per_instance=risk_config.max_open_positions_per_instance))

def check_max_daily_loss(*, risk_config: RiskConfig, daily_loss_percent: float) -> RiskRuleResult:
    if not risk_config.daily_loss_limit_enabled:
        return _allowed()
    if daily_loss_percent < risk_config.max_daily_loss_percent:
        return _allowed()
    return _blocked(build_reason(REASON_RISK_DAILY_LOSS, 'daily loss limit reached', daily_loss_percent=daily_loss_percent, max_daily_loss_percent=risk_config.max_daily_loss_percent))

def check_max_drawdown(*, risk_config: RiskConfig, drawdown_percent: float) -> RiskRuleResult:
    if not risk_config.drawdown_limit_enabled:
        return _allowed()
    if drawdown_percent < risk_config.max_drawdown_percent:
        return _allowed()
    return _blocked(build_reason(REASON_RISK_MAX_DRAWDOWN, 'drawdown limit reached', drawdown_percent=drawdown_percent, max_drawdown_percent=risk_config.max_drawdown_percent))

def evaluate_risk_rules(*, status: StatusRecord, instance_state: InstanceState, risk_config: RiskConfig, risk_context: RiskContext) -> RiskRuleResult:
    checks = (check_trade_allowed(status=status), check_max_open_positions(instance_state=instance_state, risk_config=risk_config), check_max_daily_loss(risk_config=risk_config, daily_loss_percent=risk_context.daily_loss_percent), check_max_drawdown(risk_config=risk_config, drawdown_percent=risk_context.drawdown_percent))
    for result in checks:
        if not result.allowed:
            return result
    return _allowed()
