from __future__ import annotations

from checktrader.config.models import SystemConfig
from checktrader.domain.enums import Decision, ReasonCode, Side
from checktrader.domain.models import ManagementAction, Position, RegimeSnapshot, SymbolSpecs
from checktrader.management.breakeven import breakeven_action
from checktrader.management.exits import regime_flip_action, stop_hit_action
from checktrader.management.take_profit import take_profit_action
from checktrader.management.trailing import trailing_action


def manage_position(
    position: Position,
    *,
    bid: float,
    ask: float,
    atr_value: float | None,
    regime: RegimeSnapshot,
    specs: SymbolSpecs,
    config: SystemConfig,
) -> ManagementAction:
    price = bid if position.side == Side.BUY else ask
    for a in (
        stop_hit_action(position, bid, ask),
        take_profit_action(position, bid, ask),
        regime_flip_action(position, regime.regime, config.management),
    ):
        if a.decision == Decision.CLOSE:
            return a
    for a in (
        breakeven_action(position, price, config.management, specs),
        trailing_action(position, price, atr_value, regime.regime, config.management),
    ):
        if a.decision == Decision.MODIFY:
            return a
    return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
