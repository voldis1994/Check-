from __future__ import annotations

from checktrader.config.models import ManagementConfig
from checktrader.domain.enums import Decision, MarketRegime, OrderAction, ReasonCode, Side, StrategyType
from checktrader.domain.models import ManagementAction, Position
from checktrader.management.breakeven import profit_r


def _mult(position: Position, regime: MarketRegime, config: ManagementConfig) -> float:
    if position.strategy == StrategyType.BREAKOUT:
        return config.breakout_trailing_atr_multiplier
    if position.strategy == StrategyType.RANGE_REVERSION or regime == MarketRegime.RANGE:
        return config.range_trailing_atr_multiplier
    return config.trend_trailing_atr_multiplier


def trailing_action(
    position: Position, price: float, atr_value: float | None, regime: MarketRegime, config: ManagementConfig
) -> ManagementAction:
    rr = profit_r(position, price)
    if atr_value is None or rr is None or rr < config.trailing_start_rr:
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
    mult = _mult(position, regime, config)
    candidate = price - mult * atr_value if position.side == Side.BUY else price + mult * atr_value
    if position.stop_loss is None:
        return ManagementAction(Decision.MODIFY, ReasonCode.TRAILING_MOVE, OrderAction.MODIFY, stop_loss=candidate)
    if position.side == Side.BUY and candidate > position.stop_loss:
        return ManagementAction(Decision.MODIFY, ReasonCode.TRAILING_MOVE, OrderAction.MODIFY, stop_loss=candidate)
    if position.side == Side.SELL and candidate < position.stop_loss:
        return ManagementAction(Decision.MODIFY, ReasonCode.TRAILING_MOVE, OrderAction.MODIFY, stop_loss=candidate)
    return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
