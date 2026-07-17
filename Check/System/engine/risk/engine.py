from __future__ import annotations
from dataclasses import dataclass
from engine.decision.buy import BuyCandidate
from engine.decision.engine import DecisionResult
from engine.decision.sell import SellCandidate
from engine.protocol.constants import Decision, REASON_DATA_INVALID, REASON_INVALID_VOLUME, RiskResult, Side
from engine.protocol.models import RiskConfig, StatusRecord
from engine.reason import build_reason
from engine.risk.metrics import build_risk_context
from engine.risk.position_sizing import normalize_volume_to_step
from engine.risk.rules import evaluate_risk_rules
from engine.risk.sl_tp import validate_sl_tp
from engine.state.instance_state import InstanceState
MODULE_NAME = 'risk.engine'

@dataclass(frozen=True)
class RiskEngineTradeParams:
    volume_step: float
    max_stop_loss_pips: float
    units_per_lot: float = 100000.0

@dataclass(frozen=True)
class RiskEngineResult:
    result: str
    reason: str
    position_size: float | None
    stop_loss: float | None
    take_profit: float | None

def _block(reason: str) -> RiskEngineResult:
    return RiskEngineResult(result=RiskResult.BLOCK.value, reason=reason, position_size=None, stop_loss=None, take_profit=None)

def _allow(*, position_size: float, stop_loss: float, take_profit: float) -> RiskEngineResult:
    return RiskEngineResult(result=RiskResult.ALLOW.value, reason='', position_size=position_size, stop_loss=stop_loss, take_profit=take_profit)

def _selected_candidate(*, preferred_side: str, buy_candidate: BuyCandidate, sell_candidate: SellCandidate) -> BuyCandidate | SellCandidate | None:
    if preferred_side == Side.BUY.value:
        return buy_candidate
    if preferred_side == Side.SELL.value:
        return sell_candidate
    return None

def run_risk_engine(*, decision_result: DecisionResult, risk_config: RiskConfig, instance_state: InstanceState, status: StatusRecord, trade_params: RiskEngineTradeParams, swing_low: float, swing_high: float, use_fixed_take_profit: bool=True) -> RiskEngineResult:
    if decision_result.decision in {Decision.WAIT.value, Decision.BLOCK.value}:
        return _block(decision_result.reason or f'decision is {decision_result.decision}')
    if decision_result.decision not in {Decision.BUY.value, Decision.SELL.value}:
        return _block(build_reason(REASON_DATA_INVALID, 'risk engine requires BUY or SELL decision', decision=decision_result.decision))
    risk_context = build_risk_context(status=status, instance_state=instance_state)
    rules_result = evaluate_risk_rules(status=status, instance_state=instance_state, risk_config=risk_config, risk_context=risk_context)
    if not rules_result.allowed:
        return _block(rules_result.reason or 'risk rules blocked trade')
    candidate = _selected_candidate(preferred_side=decision_result.preferred_side, buy_candidate=decision_result.buy_candidate, sell_candidate=decision_result.sell_candidate)
    if candidate is None:
        return _block(build_reason(REASON_DATA_INVALID, 'preferred side must be BUY or SELL', preferred_side=decision_result.preferred_side))
    if not candidate.valid:
        return _block(candidate.invalid_reason or 'selected candidate is invalid')
    point = instance_state.instrument_point
    pip = instance_state.instrument_pip
    if point <= 0 or pip <= 0:
        return _block(build_reason(REASON_DATA_INVALID, 'instrument point and pip must be configured', point=point, pip=pip))
    sl_tp_result = validate_sl_tp(side=decision_result.preferred_side, entry_price=candidate.entry_price, stop_loss=candidate.stop_loss, take_profit=candidate.take_profit, swing_low=swing_low, swing_high=swing_high, pip=pip, max_stop_loss_pips=trade_params.max_stop_loss_pips, require_fixed_take_profit=use_fixed_take_profit)
    if not sl_tp_result.allowed:
        return _block(sl_tp_result.reason or 'stop loss or take profit validation failed')
    broker_take_profit = sl_tp_result.take_profit if use_fixed_take_profit else 0.0
    if risk_config.fixed_lot_volume <= 0:
        return _block(build_reason(REASON_INVALID_VOLUME, 'fixed_lot_volume must be > 0; percent equity sizing is disabled', fixed_lot_volume=risk_config.fixed_lot_volume))
    volume = normalize_volume_to_step(volume=risk_config.fixed_lot_volume, volume_step=trade_params.volume_step)
    if volume <= 0:
        return _block(build_reason(REASON_INVALID_VOLUME, 'fixed lot volume is below broker minimum step', fixed_lot_volume=risk_config.fixed_lot_volume, volume_step=trade_params.volume_step))
    return _allow(position_size=volume, stop_loss=sl_tp_result.stop_loss, take_profit=broker_take_profit)
