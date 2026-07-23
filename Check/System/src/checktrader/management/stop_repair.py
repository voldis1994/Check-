"""Tighten absurd open-position stops (e.g. EURUSD 294-pip SL)."""

from __future__ import annotations

from checktrader.config.models import RiskConfig, StrategiesConfig
from checktrader.domain.enums import Decision, OrderAction, ReasonCode, Side
from checktrader.domain.models import ManagementAction, Position, SymbolSpecs
from checktrader.management.atr_stops import sanitize_atr, stop_target_distance


def repair_absurd_stop_action(
    position: Position,
    *,
    bid: float,
    ask: float,
    atr_value: float | None,
    specs: SymbolSpecs,
    strategies: StrategiesConfig,
    risk: RiskConfig,
) -> ManagementAction:
    """
    If broker SL is insanely wide vs sanitized ATR, pull it in.

    Live bug: SELL 1.13714 / SL 1.16654 = 294 pips. Next cycle → ~10 pips.
    Only tightens; never widens. Respects broker stop-level vs market.
    """
    if position.stop_loss is None:
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)

    entry = position.entry_price
    current = float(position.stop_loss)
    current_dist = abs(entry - current)
    ideal = stop_target_distance(specs, strategies, atr_value, mid=entry)
    if ideal <= 0:
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)

    cleaned = sanitize_atr(atr_value, mid=entry, specs=specs)
    # Repair when wider than max_stop_atr · sanitized ATR (or 3× ideal).
    ceiling = ideal * 3.0
    if cleaned is not None and cleaned > 0:
        ceiling = max(ceiling, float(cleaned) * float(risk.max_stop_atr))
    if current_dist <= ceiling * 1.01:
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)

    tick = specs.point if specs.point > 0 else ideal * 0.01
    min_pts = max(float(risk.min_stop_points), specs.stop_level_points, specs.freeze_level_points)
    min_dist = min_pts * specs.point if specs.point > 0 else 0.0

    if position.side == Side.BUY:
        candidate = entry - ideal
        # Keep stop below market
        max_sl = bid - min_dist
        if max_sl < candidate:
            candidate = max_sl
        if candidate >= entry:
            return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
        if candidate > current + tick:
            return ManagementAction(
                Decision.MODIFY, ReasonCode.STOP_REPAIR, OrderAction.MODIFY, stop_loss=candidate
            )
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)

    candidate = entry + ideal
    # Keep stop above market
    min_sl = ask + min_dist
    if min_sl > candidate:
        candidate = min_sl
    if candidate <= entry:
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
    if candidate < current - tick:
        return ManagementAction(
            Decision.MODIFY, ReasonCode.STOP_REPAIR, OrderAction.MODIFY, stop_loss=candidate
        )
    return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
