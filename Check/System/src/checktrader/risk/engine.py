"""Risk / lot sizing."""

from __future__ import annotations

from dataclasses import dataclass

from checktrader.config.models import RiskConfig
from checktrader.domain.enums import RiskDecision, Side
from checktrader.domain.money import SymbolSpecs, money_per_price_unit


@dataclass(frozen=True, slots=True)
class RiskApproval:
    decision: RiskDecision
    volume: float
    stop_loss: float
    take_profit: float | None
    reason: str


def _normalize_lot(volume: float, specs: SymbolSpecs) -> float:
    steps = round(volume / specs.lot_step)
    return round(steps * specs.lot_step, 8)


def approve_order(
    *,
    side: Side,
    entry: float,
    stop_loss: float,
    specs: SymbolSpecs,
    risk: RiskConfig,
    equity: float,
    free_margin: float,
) -> RiskApproval:
    if specs.tick_size <= 0 or specs.tick_value <= 0:
        return RiskApproval(RiskDecision.SYMBOL_SPEC_MISSING, 0.0, stop_loss, None, "missing tick specs")
    if entry <= 0 or stop_loss <= 0:
        return RiskApproval(RiskDecision.PRICE_INVALID, 0.0, stop_loss, None, "invalid prices")
    if side is Side.BUY and not (stop_loss < entry):
        return RiskApproval(RiskDecision.INVALID_STOP, 0.0, stop_loss, None, "BUY SL must be below entry")
    if side is Side.SELL and not (stop_loss > entry):
        return RiskApproval(RiskDecision.INVALID_STOP, 0.0, stop_loss, None, "SELL SL must be above entry")
    distance = abs(entry - stop_loss)
    distance_pips = distance / specs.pip_size if specs.pip_size > 0 else 0.0
    if distance_pips <= 0 or distance_pips > risk.maximum_stop_loss_pips:
        return RiskApproval(RiskDecision.INVALID_STOP, 0.0, stop_loss, None, "SL distance invalid")

    if risk.sizing_mode == "fixed_lot":
        volume = float(risk.fixed_lot or 0.0)
    else:
        mppu = money_per_price_unit(tick_value=specs.tick_value, tick_size=specs.tick_size, volume=1.0)
        risk_money = equity * float(risk.risk_percent or 0.0) / 100.0
        raw = risk_money / (distance * mppu) if distance * mppu > 0 else 0.0
        volume = raw
    if risk.allow_lot_normalization:
        volume = _normalize_lot(volume, specs)
    if volume < specs.minimum_lot or volume > specs.maximum_lot:
        return RiskApproval(RiskDecision.INVALID_VOLUME, 0.0, stop_loss, None, "lot outside broker bounds")
    # exact step check without silent normalize when disabled
    steps = volume / specs.lot_step
    if abs(steps - round(steps)) > 1e-8 and not risk.allow_lot_normalization:
        return RiskApproval(RiskDecision.INVALID_VOLUME, 0.0, stop_loss, None, "lot not aligned to lot_step")
    # crude margin gate
    if free_margin <= 0:
        return RiskApproval(RiskDecision.MARGIN_INSUFFICIENT, 0.0, stop_loss, None, "no free margin")
    rr = risk.minimum_reward_risk
    tp_distance = distance * rr
    take_profit = entry + tp_distance if side is Side.BUY else entry - tp_distance
    return RiskApproval(RiskDecision.APPROVED, volume, stop_loss, round(take_profit, specs.digits), "ok")
