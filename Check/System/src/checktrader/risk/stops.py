from __future__ import annotations

from checktrader.config.models import RiskConfig
from checktrader.domain.enums import ReasonCode, Side
from checktrader.domain.models import StrategySignal, SymbolSpecs


def stop_distance_points(signal: StrategySignal, specs: SymbolSpecs) -> float:
    return abs(signal.entry_price - signal.stop_loss) / specs.point


def validate_stop_distance(
    signal: StrategySignal, specs: SymbolSpecs, config: RiskConfig, atr_value: float | None = None
) -> ReasonCode:
    distance = stop_distance_points(signal, specs)
    # Stop must be at least max(min_stop_points, stop_level_points, freeze_level_points) away from entry
    minimum = max(config.min_stop_points, specs.stop_level_points, specs.freeze_level_points)
    if distance < minimum:
        return ReasonCode.RISK_STOP_TOO_CLOSE
    if distance > config.max_stop_points:
        return ReasonCode.RISK_STOP_TOO_FAR
    # ATR-based ceiling (if ATR is available)
    if atr_value is not None and atr_value > 0:
        stop_atr = abs(signal.entry_price - signal.stop_loss) / atr_value
        if stop_atr > config.max_stop_atr:
            return ReasonCode.STOP_TOO_LARGE
    return ReasonCode.RISK_ACCEPTED


def validate_reward_risk(signal: StrategySignal, config: RiskConfig) -> ReasonCode:
    if signal.take_profit is None:
        return ReasonCode.RISK_ACCEPTED
    risk = abs(signal.entry_price - signal.stop_loss)
    reward = abs(signal.take_profit - signal.entry_price)
    if risk <= 0.0:
        return ReasonCode.RISK_REWARD_TOO_LOW
    if config.min_reward_risk > 0.0 and reward / risk < config.min_reward_risk:
        return ReasonCode.RISK_REWARD_TOO_LOW
    # Directional sanity
    if signal.side == Side.BUY and not (signal.stop_loss < signal.entry_price < signal.take_profit):
        return ReasonCode.RISK_REWARD_TOO_LOW
    if signal.side == Side.SELL and not (signal.take_profit < signal.entry_price < signal.stop_loss):
        return ReasonCode.RISK_REWARD_TOO_LOW
    return ReasonCode.RISK_ACCEPTED
