"""Centralized signal-quality gates for BUY / SELL / WAIT decisions.

Directional scores (momentum, trend, structure, pressure) choose the side.
Market quality (behavior, impact, context) decides whether the market is
tradeable. Absolute score floors, score deltas, confirmations, cooldown, and
duplicate fingerprints reduce M1 noise entries.

A setup fingerprint identifies one market impulse / structure setup across
consecutive closed bars. It must NOT include the current signal candle time or
the moving candidate entry/close price.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from hashlib import sha256
from math import isfinite
from typing import Any, Mapping
from engine.analysis.structure import normalize_price_level
from engine.decision.reason import build_reason
from engine.protocol.constants import (
    REASON_CODE_DESCRIPTIONS,
    REASON_DATA_INVALID,
    REASON_DUPLICATE_SIGNAL,
    REASON_INSUFFICIENT_DIRECTIONAL_CONFIRMATIONS,
    REASON_MARKET_QUALITY_TOO_LOW,
    REASON_NO_VALID_SETUP,
    REASON_SIGNAL_DELTA_TOO_SMALL,
    REASON_SIGNAL_SCORE_BELOW_MINIMUM,
    REASON_TRADE_COOLDOWN_ACTIVE,
    Side,
    TIMEFRAME_M1,
)

DIRECTIONAL_COMPONENT_KEYS: tuple[str, ...] = ('momentum', 'trend', 'structure', 'pressure')
QUALITY_COMPONENT_KEYS: tuple[str, ...] = ('behavior', 'impact', 'context')
_CONFIRMATION_NEUTRAL_BAND = 0.05

@dataclass(frozen=True)
class ComponentConfirmation:
    """One directional component's vote."""

    name: str
    direction: str
    confidence: float
    buy_value: float
    sell_value: float

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'direction': self.direction,
            'confidence': self.confidence,
            'buy_value': self.buy_value,
            'sell_value': self.sell_value,
        }

@dataclass(frozen=True)
class SignalQualityResult:
    """Structured output of the centralized signal-quality check."""

    decision: str
    winning_side: str
    winning_score: float
    losing_score: float
    score_delta: float
    passed: bool
    reason_code: str | None
    human_readable_reason: str
    market_quality_score: float
    confirmations: tuple[ComponentConfirmation, ...] = ()
    confirmation_count: int = 0
    fingerprint: str | None = None
    cooldown_bars_remaining: int = 0
    signal_candle_timestamp: str | None = None
    setup_origin_timestamp: str | None = None
    setup_type: str | None = None
    structure_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'decision': self.decision,
            'winning_side': self.winning_side,
            'winning_score': self.winning_score,
            'losing_score': self.losing_score,
            'score_delta': self.score_delta,
            'passed': self.passed,
            'reason_code': self.reason_code,
            'human_readable_reason': self.human_readable_reason,
            'market_quality_score': self.market_quality_score,
            'confirmations': [item.to_dict() for item in self.confirmations],
            'confirmation_count': self.confirmation_count,
            'fingerprint': self.fingerprint,
            'cooldown_bars_remaining': self.cooldown_bars_remaining,
            'signal_candle_timestamp': self.signal_candle_timestamp,
            'setup_origin_timestamp': self.setup_origin_timestamp,
            'setup_type': self.setup_type,
            'structure_id': self.structure_id,
            'details': dict(self.details),
        }

def default_signal_quality_dict() -> dict[str, float | int]:
    """Safe defaults when ``signal_quality`` is omitted from config."""
    return {
        'minimum_signal_score': 0.65,
        'minimum_score_delta': 0.15,
        'minimum_market_quality': 0.60,
        'minimum_directional_confirmations': 3,
        'cooldown_bars_after_trade': 3,
        'cooldown_bars_after_loss': 5,
        'duplicate_signal_expiry_bars': 10,
    }

def calculate_directional_score(component_scores: Mapping[str, float], weights: Mapping[str, float]) -> float:
    """Weighted average of directional components only (0..1)."""
    total_weight = 0.0
    weighted = 0.0
    for key in DIRECTIONAL_COMPONENT_KEYS:
        weight = float(weights.get(key, 0.0))
        if weight <= 0:
            continue
        value = float(component_scores.get(key, 0.5))
        weighted += value * weight
        total_weight += weight
    if total_weight <= 0:
        return 0.0
    return weighted / total_weight

def calculate_market_quality_score(component_scores: Mapping[str, float]) -> float:
    """Average of behavior / impact / context (already normalized 0..1)."""
    values = [float(component_scores.get(key, 0.5)) for key in QUALITY_COMPONENT_KEYS]
    if not values:
        return 0.0
    return sum(values) / len(values)

def build_component_confirmations(*, buy_components: Mapping[str, float], sell_components: Mapping[str, float]) -> tuple[ComponentConfirmation, ...]:
    """Compare buy vs sell directional components into BUY/SELL/NEUTRAL votes."""
    confirmations: list[ComponentConfirmation] = []
    for name in DIRECTIONAL_COMPONENT_KEYS:
        buy_value = float(buy_components.get(name, 0.5))
        sell_value = float(sell_components.get(name, 0.5))
        delta = buy_value - sell_value
        if abs(delta) < _CONFIRMATION_NEUTRAL_BAND:
            direction = Side.NONE.value
            confidence = 1.0 - abs(delta)
        elif delta > 0:
            direction = Side.BUY.value
            confidence = min(1.0, abs(delta) + 0.5 * buy_value)
        else:
            direction = Side.SELL.value
            confidence = min(1.0, abs(delta) + 0.5 * sell_value)
        confirmations.append(ComponentConfirmation(name=name, direction=direction, confidence=confidence, buy_value=buy_value, sell_value=sell_value))
    return tuple(confirmations)

def count_directional_confirmations(confirmations: tuple[ComponentConfirmation, ...], side: str) -> int:
    return sum(1 for item in confirmations if item.direction == side)

def build_setup_fingerprint(
    *,
    symbol: str,
    direction: str,
    setup_type: str,
    structure_id: str,
    setup_origin_timestamp: str,
    structure_level: float,
    digits: int = 5,
    timeframe: str = TIMEFRAME_M1,
) -> str:
    """Stable setup identity for duplicate-signal protection.

    Identity is independent of the current signal candle. Use
    ``signal_candle_timestamp`` separately for audit metadata.
    """
    level = normalize_price_level(structure_level, digits=digits)
    canonical = '|'.join(
        (
            symbol.upper(),
            timeframe,
            direction.upper(),
            setup_type,
            structure_id,
            setup_origin_timestamp,
            level,
        )
    )
    digest = sha256(canonical.encode('utf-8')).hexdigest()[:20]
    return f'{canonical}|{digest}'

def build_signal_fingerprint(
    *,
    symbol: str,
    side: str,
    candle_time_utc: str | None = None,
    structure_level: float,
    setup_type: str = 'directional',
    structure_id: str = '',
    setup_origin_timestamp: str | None = None,
    digits: int = 5,
    timeframe: str = TIMEFRAME_M1,
) -> str:
    """Build a setup fingerprint.

    ``candle_time_utc`` is accepted only for backward-compatible call sites and
    is intentionally ignored for identity. Prefer ``build_setup_fingerprint``.
    """
    del candle_time_utc  # never part of setup identity
    origin = setup_origin_timestamp or ''
    resolved_structure_id = structure_id or f'legacy|{normalize_price_level(structure_level, digits=digits)}|{setup_type}'
    return build_setup_fingerprint(
        symbol=symbol,
        direction=side,
        setup_type=setup_type,
        structure_id=resolved_structure_id,
        setup_origin_timestamp=origin,
        structure_level=structure_level,
        digits=digits,
        timeframe=timeframe,
    )

def _scores_are_numeric(buy_score: float, sell_score: float) -> bool:
    return isfinite(float(buy_score)) and isfinite(float(sell_score))

def _wait_result(
    *,
    reason_code: str,
    message: str,
    winning_side: str,
    winning_score: float,
    losing_score: float,
    score_delta: float,
    market_quality_score: float,
    confirmations: tuple[ComponentConfirmation, ...] = (),
    confirmation_count: int = 0,
    fingerprint: str | None = None,
    cooldown_bars_remaining: int = 0,
    signal_candle_timestamp: str | None = None,
    setup_origin_timestamp: str | None = None,
    setup_type: str | None = None,
    structure_id: str | None = None,
    **details: Any,
) -> SignalQualityResult:
    human = REASON_CODE_DESCRIPTIONS.get(reason_code, message)
    reason = build_reason(reason_code, message, **details)
    return SignalQualityResult(
        decision='WAIT',
        winning_side=winning_side,
        winning_score=winning_score,
        losing_score=losing_score,
        score_delta=score_delta,
        passed=False,
        reason_code=reason_code,
        human_readable_reason=f'{human}. {reason}',
        market_quality_score=market_quality_score,
        confirmations=confirmations,
        confirmation_count=confirmation_count,
        fingerprint=fingerprint,
        cooldown_bars_remaining=cooldown_bars_remaining,
        signal_candle_timestamp=signal_candle_timestamp,
        setup_origin_timestamp=setup_origin_timestamp,
        setup_type=setup_type,
        structure_id=structure_id,
        details=dict(details),
    )

def evaluate_signal_quality(
    *,
    buy_score: float,
    sell_score: float,
    buy_valid: bool,
    sell_valid: bool,
    buy_components: Mapping[str, float],
    sell_components: Mapping[str, float],
    market_quality_score: float,
    signal_quality_config: Any,
    symbol: str,
    candle_time_utc: str,
    structure_level: float,
    cooldown_bars_remaining: int = 0,
    last_trade_result: str | None = None,
    last_trade_close_time_utc: str | None = None,
    last_trade_close_bar_utc: str | None = None,
    active_fingerprints: Mapping[str, str] | None = None,
    setup_origin_timestamp: str = '',
    structure_id: str = '',
    setup_type: str = 'directional',
    digits: int = 5,
    timeframe: str = TIMEFRAME_M1,
) -> SignalQualityResult:
    """Run all signal-quality gates and return BUY, SELL, or WAIT.

    Only closed-bar inputs should be passed (``candle_time_utc`` of the last
    closed market bar). No future bars are consulted.

    Score delta is always enforced when both BUY and SELL scores are finite
    numbers — including when the opposite candidate is invalid for another rule.
    """
    confirmations = build_component_confirmations(buy_components=buy_components, sell_components=sell_components)
    score_delta = abs(float(buy_score) - float(sell_score))
    active_fingerprints = active_fingerprints or {}
    signal_meta = {
        'signal_candle_timestamp': candle_time_utc,
        'setup_origin_timestamp': setup_origin_timestamp or None,
        'setup_type': setup_type,
        'structure_id': structure_id or None,
    }

    if not _scores_are_numeric(buy_score, sell_score):
        return _wait_result(
            reason_code=REASON_DATA_INVALID,
            message='buy or sell score is not a finite number',
            winning_side=Side.NONE.value,
            winning_score=0.0,
            losing_score=0.0,
            score_delta=0.0,
            market_quality_score=market_quality_score,
            confirmations=confirmations,
            buy_score=buy_score,
            sell_score=sell_score,
            **signal_meta,
        )

    if cooldown_bars_remaining > 0:
        return _wait_result(
            reason_code=REASON_TRADE_COOLDOWN_ACTIVE,
            message='trade cooldown is active',
            winning_side=Side.NONE.value,
            winning_score=max(buy_score, sell_score),
            losing_score=min(buy_score, sell_score),
            score_delta=score_delta,
            market_quality_score=market_quality_score,
            confirmations=confirmations,
            cooldown_bars_remaining=cooldown_bars_remaining,
            cooldown_bars_remaining_value=cooldown_bars_remaining,
            last_trade_result=last_trade_result,
            last_trade_close_time_utc=last_trade_close_time_utc,
            last_trade_close_bar_utc=last_trade_close_bar_utc,
            **signal_meta,
        )

    if market_quality_score < float(signal_quality_config.minimum_market_quality):
        return _wait_result(
            reason_code=REASON_MARKET_QUALITY_TOO_LOW,
            message='market quality below minimum',
            winning_side=Side.NONE.value,
            winning_score=max(buy_score, sell_score),
            losing_score=min(buy_score, sell_score),
            score_delta=score_delta,
            market_quality_score=market_quality_score,
            confirmations=confirmations,
            market_quality_score_value=market_quality_score,
            minimum_market_quality=float(signal_quality_config.minimum_market_quality),
            **signal_meta,
        )

    if not buy_valid and not sell_valid:
        return _wait_result(
            reason_code=REASON_NO_VALID_SETUP,
            message='no valid buy or sell setup',
            winning_side=Side.NONE.value,
            winning_score=0.0,
            losing_score=0.0,
            score_delta=0.0,
            market_quality_score=market_quality_score,
            confirmations=confirmations,
            **signal_meta,
        )

    if buy_valid and sell_valid:
        if buy_score > sell_score:
            winning_side, winning_score, losing_score = Side.BUY.value, float(buy_score), float(sell_score)
        elif sell_score > buy_score:
            winning_side, winning_score, losing_score = Side.SELL.value, float(sell_score), float(buy_score)
        else:
            return _wait_result(
                reason_code=REASON_SIGNAL_DELTA_TOO_SMALL,
                message='buy and sell scores are equal',
                winning_side=Side.NONE.value,
                winning_score=float(buy_score),
                losing_score=float(sell_score),
                score_delta=0.0,
                market_quality_score=market_quality_score,
                confirmations=confirmations,
                buy_score=float(buy_score),
                sell_score=float(sell_score),
                minimum_score_delta=float(signal_quality_config.minimum_score_delta),
                **signal_meta,
            )
    elif buy_valid:
        winning_side, winning_score, losing_score = Side.BUY.value, float(buy_score), float(sell_score)
    else:
        winning_side, winning_score, losing_score = Side.SELL.value, float(sell_score), float(buy_score)

    score_delta = abs(winning_score - losing_score)
    confirmation_count = count_directional_confirmations(confirmations, winning_side)
    fingerprint = build_setup_fingerprint(
        symbol=symbol,
        direction=winning_side,
        setup_type=setup_type,
        structure_id=structure_id or f'legacy|{normalize_price_level(structure_level, digits=digits)}',
        setup_origin_timestamp=setup_origin_timestamp,
        structure_level=structure_level,
        digits=digits,
        timeframe=timeframe,
    )

    if winning_score < float(signal_quality_config.minimum_signal_score):
        return _wait_result(
            reason_code=REASON_SIGNAL_SCORE_BELOW_MINIMUM,
            message='winning score below minimum_signal_score',
            winning_side=winning_side,
            winning_score=winning_score,
            losing_score=losing_score,
            score_delta=score_delta,
            market_quality_score=market_quality_score,
            confirmations=confirmations,
            confirmation_count=confirmation_count,
            fingerprint=fingerprint,
            buy_score=float(buy_score),
            sell_score=float(sell_score),
            winning_score_value=winning_score,
            minimum_signal_score=float(signal_quality_config.minimum_signal_score),
            **signal_meta,
        )

    # Always enforce delta when both numeric scores exist — even if the opposite
    # candidate is invalid for an unrelated filter.
    if score_delta < float(signal_quality_config.minimum_score_delta):
        return _wait_result(
            reason_code=REASON_SIGNAL_DELTA_TOO_SMALL,
            message='score delta below minimum_score_delta',
            winning_side=winning_side,
            winning_score=winning_score,
            losing_score=losing_score,
            score_delta=score_delta,
            market_quality_score=market_quality_score,
            confirmations=confirmations,
            confirmation_count=confirmation_count,
            fingerprint=fingerprint,
            buy_score=float(buy_score),
            sell_score=float(sell_score),
            score_delta_value=score_delta,
            minimum_score_delta=float(signal_quality_config.minimum_score_delta),
            buy_valid=buy_valid,
            sell_valid=sell_valid,
            **signal_meta,
        )

    if confirmation_count < int(signal_quality_config.minimum_directional_confirmations):
        return _wait_result(
            reason_code=REASON_INSUFFICIENT_DIRECTIONAL_CONFIRMATIONS,
            message='insufficient directional confirmations',
            winning_side=winning_side,
            winning_score=winning_score,
            losing_score=losing_score,
            score_delta=score_delta,
            market_quality_score=market_quality_score,
            confirmations=confirmations,
            confirmation_count=confirmation_count,
            fingerprint=fingerprint,
            confirmation_count_value=confirmation_count,
            minimum_directional_confirmations=int(signal_quality_config.minimum_directional_confirmations),
            component_directions={item.name: item.direction for item in confirmations},
            component_confidences={item.name: item.confidence for item in confirmations},
            **signal_meta,
        )

    if fingerprint in active_fingerprints:
        return _wait_result(
            reason_code=REASON_DUPLICATE_SIGNAL,
            message='duplicate signal fingerprint still active',
            winning_side=winning_side,
            winning_score=winning_score,
            losing_score=losing_score,
            score_delta=score_delta,
            market_quality_score=market_quality_score,
            confirmations=confirmations,
            confirmation_count=confirmation_count,
            fingerprint=fingerprint,
            fingerprint_value=fingerprint,
            fingerprint_expiry_bar_utc=active_fingerprints.get(fingerprint),
            **signal_meta,
        )

    human = f'{winning_side} passed signal quality gates'
    return SignalQualityResult(
        decision=winning_side,
        winning_side=winning_side,
        winning_score=winning_score,
        losing_score=losing_score,
        score_delta=score_delta,
        passed=True,
        reason_code=None,
        human_readable_reason=human,
        market_quality_score=market_quality_score,
        confirmations=confirmations,
        confirmation_count=confirmation_count,
        fingerprint=fingerprint,
        cooldown_bars_remaining=0,
        signal_candle_timestamp=candle_time_utc,
        setup_origin_timestamp=setup_origin_timestamp or None,
        setup_type=setup_type,
        structure_id=structure_id or None,
        details={
            'buy_score': float(buy_score),
            'sell_score': float(sell_score),
            'minimum_signal_score': float(signal_quality_config.minimum_signal_score),
            'minimum_score_delta': float(signal_quality_config.minimum_score_delta),
            'minimum_market_quality': float(signal_quality_config.minimum_market_quality),
            'minimum_directional_confirmations': int(signal_quality_config.minimum_directional_confirmations),
            'component_directions': {item.name: item.direction for item in confirmations},
            'component_confidences': {item.name: item.confidence for item in confirmations},
            'buy_valid': buy_valid,
            'sell_valid': sell_valid,
        },
    )
