from __future__ import annotations

from datetime import UTC, datetime

from checktrader.config.models import ManagementConfig
from checktrader.domain.enums import Decision, MarketRegime, OrderAction, ReasonCode, Side, StrategyType
from checktrader.domain.models import ManagementAction, Position


def stop_hit_action(position: Position, bid: float, ask: float) -> ManagementAction:
    if position.stop_loss is None:
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
    if position.side == Side.BUY and bid <= position.stop_loss:
        return ManagementAction(Decision.CLOSE, ReasonCode.EXIT_STOP_HIT, OrderAction.CLOSE, close_fraction=1.0)
    if position.side == Side.SELL and ask >= position.stop_loss:
        return ManagementAction(Decision.CLOSE, ReasonCode.EXIT_STOP_HIT, OrderAction.CLOSE, close_fraction=1.0)
    return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)


def regime_flip_action(
    position: Position,
    regime: MarketRegime,
    config: ManagementConfig,
    *,
    now: datetime | None = None,
) -> ManagementAction:
    """
    Optional opposite-regime exit.

    Default is OFF — with a 5s cycle this was closing brand-new trades in ~6 seconds.
    When enabled, respect regime_flip_min_hold_seconds so entries can breathe.
    """
    if not config.exit_on_regime_flip or position.strategy == StrategyType.RANGE_REVERSION:
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)

    hold_s = float(config.regime_flip_min_hold_seconds)
    if hold_s > 0:
        ts = now or datetime.now(UTC)
        opened = position.opened_at
        if opened.tzinfo is None:
            opened = opened.replace(tzinfo=UTC)
        age = (ts - opened).total_seconds()
        if age < hold_s:
            return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)

    if position.side == Side.BUY and regime == MarketRegime.TREND_DOWN:
        return ManagementAction(Decision.CLOSE, ReasonCode.EXIT_REGIME_FLIP, OrderAction.CLOSE, close_fraction=1.0)
    if position.side == Side.SELL and regime == MarketRegime.TREND_UP:
        return ManagementAction(Decision.CLOSE, ReasonCode.EXIT_REGIME_FLIP, OrderAction.CLOSE, close_fraction=1.0)
    return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
