"""ATR trailing stop — lock-back distance is ATR-based (cross-market).

Reference: NATURALGAS Capital.com point≈0.001 → 20 points = 0.02 price.
With typical M15 ATR≈0.04, lock ≈ 0.50 * ATR ≈ 20 points.
Same ATR fraction is used on EURUSD / other symbols so point size never matters.
"""

from __future__ import annotations

from checktrader.config.models import ManagementConfig
from checktrader.domain.enums import Decision, MarketRegime, OrderAction, ReasonCode, Side
from checktrader.domain.models import ManagementAction, Position


def trail_lock_distance(atr_value: float, config: ManagementConfig) -> float:
    """Price distance to trail behind price (= trailing_lock_atr * ATR)."""
    return max(atr_value * config.trailing_lock_atr, atr_value * 0.05)


def trailing_action(
    position: Position, price: float, atr_value: float | None, regime: MarketRegime, config: ManagementConfig
) -> ManagementAction:
    del regime  # lock is ATR-only; strategy/regime mults no longer starve the trail
    if atr_value is None or atr_value <= 0:
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)

    lock = trail_lock_distance(atr_value, config)
    if position.side == Side.BUY:
        profit = price - position.entry_price
        # Need more than one lock of profit so SL can sit above entry (past BE).
        if profit < lock * 1.05:
            return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
        candidate = price - lock
        if position.stop_loss is None or candidate > position.stop_loss:
            return ManagementAction(Decision.MODIFY, ReasonCode.TRAILING_MOVE, OrderAction.MODIFY, stop_loss=candidate)
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)

    profit = position.entry_price - price
    if profit < lock * 1.05:
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
    candidate = price + lock
    if position.stop_loss is None or candidate < position.stop_loss:
        return ManagementAction(Decision.MODIFY, ReasonCode.TRAILING_MOVE, OrderAction.MODIFY, stop_loss=candidate)
    return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
