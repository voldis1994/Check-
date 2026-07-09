from __future__ import annotations
from engine.protocol.models import StatusRecord
from engine.risk.rules import RiskContext
from engine.state.instance_state import InstanceState

def compute_drawdown_percent(*, balance: float, equity: float, peak_equity: float | None) -> float:
    reference = peak_equity if peak_equity is not None and peak_equity > 0 else balance
    if reference <= 0:
        return 0.0
    drawdown = reference - equity
    if drawdown <= 0:
        return 0.0
    return drawdown / reference * 100.0

def compute_daily_loss_percent(*, equity: float, day_start_balance: float | None) -> float:
    if day_start_balance is None or day_start_balance <= 0:
        return 0.0
    loss = day_start_balance - equity
    if loss <= 0:
        return 0.0
    return loss / day_start_balance * 100.0

def build_risk_context(*, status: StatusRecord, instance_state: InstanceState) -> RiskContext:
    return RiskContext(daily_loss_percent=compute_daily_loss_percent(equity=status.equity, day_start_balance=instance_state.day_start_balance), drawdown_percent=compute_drawdown_percent(balance=status.balance, equity=status.equity, peak_equity=instance_state.peak_equity))
