"""Fixed-lot risk approval — never resize lots."""

from __future__ import annotations

from dataclasses import dataclass

from checktrader.config.models import PositionSizingConfig
from checktrader.domain.enums import RiskDecision, Side
from checktrader.domain.money import SymbolSpecs, round_price
from checktrader.risk.broker_constraints import freeze_level_price, min_stop_distance, stop_level_price
from checktrader.risk.lot_size import validate_fixed_lot
from checktrader.risk.margin import margin_allows_fixed_lot
from checktrader.risk.stop_loss import atr_to_price_distance


@dataclass(frozen=True, slots=True)
class RiskApproval:
    decision: RiskDecision
    volume: float
    stop_loss: float
    take_profit: float | None
    reason: str
    requested_lot: float = 0.0
    minimum_lot: float = 0.0
    maximum_lot: float = 0.0
    lot_step: float = 0.0
    symbol: str = ""
    broker_server: str = ""


def approve_order(
    *,
    side: Side,
    entry: float,
    stop_loss: float,
    specs: SymbolSpecs,
    sizing: PositionSizingConfig,
    atr: float,
    maximum_stop_atr: float,
    free_margin: float,
    broker_server: str = "",
    fixed_take_profit_enabled: bool = False,
    minimum_reward_risk: float = 1.5,
    bid: float | None = None,
    ask: float | None = None,
) -> RiskApproval:
    """Approve OPEN using exactly ``sizing.fixed_lot`` — never normalize."""
    base = RiskApproval(
        RiskDecision.RISK_CONFIG_INVALID,
        0.0,
        stop_loss,
        None,
        "",
        requested_lot=float(sizing.fixed_lot),
        minimum_lot=float(specs.minimum_lot),
        maximum_lot=float(specs.maximum_lot),
        lot_step=float(specs.lot_step),
        symbol=specs.symbol,
        broker_server=broker_server,
    )
    if sizing.mode != "fixed_lot" or sizing.allow_broker_lot_normalization:
        return RiskApproval(
            RiskDecision.RISK_CONFIG_INVALID,
            0.0,
            stop_loss,
            None,
            "only fixed_lot without broker normalization is allowed",
            requested_lot=base.requested_lot,
            minimum_lot=base.minimum_lot,
            maximum_lot=base.maximum_lot,
            lot_step=base.lot_step,
            symbol=specs.symbol,
            broker_server=broker_server,
        )
    if specs.tick_size <= 0 or specs.tick_value <= 0:
        return RiskApproval(
            RiskDecision.SYMBOL_SPEC_MISSING,
            0.0,
            stop_loss,
            None,
            "missing tick specs",
            requested_lot=base.requested_lot,
            minimum_lot=base.minimum_lot,
            maximum_lot=base.maximum_lot,
            lot_step=base.lot_step,
            symbol=specs.symbol,
            broker_server=broker_server,
        )
    if entry <= 0 or stop_loss <= 0:
        return RiskApproval(
            RiskDecision.PRICE_INVALID,
            0.0,
            stop_loss,
            None,
            "invalid prices",
            requested_lot=base.requested_lot,
            minimum_lot=base.minimum_lot,
            maximum_lot=base.maximum_lot,
            lot_step=base.lot_step,
            symbol=specs.symbol,
            broker_server=broker_server,
        )
    if bid is not None and ask is not None and (bid <= 0 or ask <= 0 or ask < bid):
        return RiskApproval(
            RiskDecision.PRICE_INVALID,
            0.0,
            stop_loss,
            None,
            "invalid bid/ask",
            requested_lot=base.requested_lot,
            minimum_lot=base.minimum_lot,
            maximum_lot=base.maximum_lot,
            lot_step=base.lot_step,
            symbol=specs.symbol,
            broker_server=broker_server,
        )
    if side is Side.BUY and not (stop_loss < entry):
        return RiskApproval(
            RiskDecision.INVALID_STOP,
            0.0,
            stop_loss,
            None,
            "BUY SL must be below entry",
            requested_lot=base.requested_lot,
            minimum_lot=base.minimum_lot,
            maximum_lot=base.maximum_lot,
            lot_step=base.lot_step,
            symbol=specs.symbol,
            broker_server=broker_server,
        )
    if side is Side.SELL and not (stop_loss > entry):
        return RiskApproval(
            RiskDecision.INVALID_STOP,
            0.0,
            stop_loss,
            None,
            "SELL SL must be above entry",
            requested_lot=base.requested_lot,
            minimum_lot=base.minimum_lot,
            maximum_lot=base.maximum_lot,
            lot_step=base.lot_step,
            symbol=specs.symbol,
            broker_server=broker_server,
        )

    distance = abs(entry - stop_loss)
    max_dist = atr_to_price_distance(atr, maximum_stop_atr, specs)
    if atr <= 0 or max_dist <= 0 or distance > max_dist + float(specs.tick_size):
        return RiskApproval(
            RiskDecision.INVALID_STOP,
            0.0,
            stop_loss,
            None,
            "SL distance exceeds maximum_stop_atr",
            requested_lot=base.requested_lot,
            minimum_lot=base.minimum_lot,
            maximum_lot=base.maximum_lot,
            lot_step=base.lot_step,
            symbol=specs.symbol,
            broker_server=broker_server,
        )

    min_dist = min_stop_distance(specs)
    if distance + 1e-12 < stop_level_price(specs):
        return RiskApproval(
            RiskDecision.STOP_LEVEL_VIOLATION,
            0.0,
            stop_loss,
            None,
            "stop_level violation",
            requested_lot=base.requested_lot,
            minimum_lot=base.minimum_lot,
            maximum_lot=base.maximum_lot,
            lot_step=base.lot_step,
            symbol=specs.symbol,
            broker_server=broker_server,
        )
    if distance + 1e-12 < freeze_level_price(specs):
        return RiskApproval(
            RiskDecision.FREEZE_LEVEL_VIOLATION,
            0.0,
            stop_loss,
            None,
            "freeze_level violation",
            requested_lot=base.requested_lot,
            minimum_lot=base.minimum_lot,
            maximum_lot=base.maximum_lot,
            lot_step=base.lot_step,
            symbol=specs.symbol,
            broker_server=broker_server,
        )
    if min_dist > 0 and distance + 1e-12 < min_dist:
        return RiskApproval(
            RiskDecision.INVALID_STOP,
            0.0,
            stop_loss,
            None,
            "SL inside stop/freeze level",
            requested_lot=base.requested_lot,
            minimum_lot=base.minimum_lot,
            maximum_lot=base.maximum_lot,
            lot_step=base.lot_step,
            symbol=specs.symbol,
            broker_server=broker_server,
        )

    lot_check = validate_fixed_lot(specs, sizing.fixed_lot)
    if not lot_check.ok:
        return RiskApproval(
            RiskDecision.FIXED_LOT_NOT_SUPPORTED,
            0.0,
            stop_loss,
            None,
            lot_check.detail,
            requested_lot=lot_check.requested_lot,
            minimum_lot=lot_check.minimum_lot,
            maximum_lot=lot_check.maximum_lot,
            lot_step=lot_check.lot_step,
            symbol=specs.symbol,
            broker_server=broker_server,
        )

    volume = lot_check.lot
    if not margin_allows_fixed_lot(free_margin=free_margin, fixed_lot=volume):
        return RiskApproval(
            RiskDecision.MARGIN_INSUFFICIENT_FOR_FIXED_LOT,
            0.0,
            stop_loss,
            None,
            "insufficient margin for fixed_lot",
            requested_lot=volume,
            minimum_lot=lot_check.minimum_lot,
            maximum_lot=lot_check.maximum_lot,
            lot_step=lot_check.lot_step,
            symbol=specs.symbol,
            broker_server=broker_server,
        )

    take_profit: float | None = None
    if fixed_take_profit_enabled:
        tp_distance = distance * float(minimum_reward_risk)
        raw_tp = entry + tp_distance if side is Side.BUY else entry - tp_distance
        take_profit = round_price(raw_tp, specs.digits)

    return RiskApproval(
        RiskDecision.APPROVED,
        volume,
        stop_loss,
        take_profit,
        "ok",
        requested_lot=volume,
        minimum_lot=lot_check.minimum_lot,
        maximum_lot=lot_check.maximum_lot,
        lot_step=lot_check.lot_step,
        symbol=specs.symbol,
        broker_server=broker_server,
    )
