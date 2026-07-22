from __future__ import annotations
import pytest
from engine.core.config import parse_config_payload
from engine.decision.signal_quality import (
    SignalQualityResult,
    build_component_confirmations,
    build_signal_fingerprint,
    calculate_directional_score,
    calculate_market_quality_score,
    count_directional_confirmations,
    default_signal_quality_dict,
    evaluate_signal_quality,
)
from engine.protocol.constants import (
    REASON_DUPLICATE_SIGNAL,
    REASON_INSUFFICIENT_DIRECTIONAL_CONFIRMATIONS,
    REASON_MARKET_QUALITY_TOO_LOW,
    REASON_NO_VALID_SETUP,
    REASON_SIGNAL_DELTA_TOO_SMALL,
    REASON_SIGNAL_SCORE_BELOW_MINIMUM,
    REASON_TRADE_COOLDOWN_ACTIVE,
    Side,
)
from engine.protocol.errors import ValidationError
from engine.protocol.models import SignalQualityConfig
from tests.core.config_payload import valid_system_config_payload

def _cfg(**overrides: float | int) -> SignalQualityConfig:
    payload = default_signal_quality_dict()
    payload.update(overrides)
    return SignalQualityConfig(**payload)

def _buy_components(*, strong: bool=True) -> dict[str, float]:
    if strong:
        return {'momentum': 0.85, 'trend': 0.82, 'structure': 0.80, 'pressure': 0.78, 'behavior': 0.75, 'impact': 0.75, 'context': 0.75}
    return {'momentum': 0.55, 'trend': 0.54, 'structure': 0.52, 'pressure': 0.51, 'behavior': 0.70, 'impact': 0.70, 'context': 0.70}

def _sell_components(*, weak: bool=True) -> dict[str, float]:
    if weak:
        return {'momentum': 0.35, 'trend': 0.32, 'structure': 0.30, 'pressure': 0.28, 'behavior': 0.75, 'impact': 0.75, 'context': 0.75}
    return {'momentum': 0.70, 'trend': 0.68, 'structure': 0.66, 'pressure': 0.64, 'behavior': 0.75, 'impact': 0.75, 'context': 0.75}

def _quality_kwargs(**overrides: object) -> dict[str, object]:
    buy = _buy_components()
    sell = _sell_components()
    base: dict[str, object] = {
        'buy_score': 0.80,
        'sell_score': 0.30,
        'buy_valid': True,
        'sell_valid': True,
        'buy_components': buy,
        'sell_components': sell,
        'market_quality_score': 0.75,
        'signal_quality_config': _cfg(),
        'symbol': 'EURUSD',
        'candle_time_utc': '2026-07-07T06:02:00.000Z',
        'structure_level': 1.10310,
        'cooldown_bars_remaining': 0,
        'active_fingerprints': {},
    }
    base.update(overrides)
    return base

def test_defaults_match_documented_values() -> None:
    defaults = default_signal_quality_dict()
    assert defaults == {
        'minimum_signal_score': 0.65,
        'minimum_score_delta': 0.15,
        'minimum_market_quality': 0.60,
        'minimum_directional_confirmations': 3,
        'cooldown_bars_after_trade': 3,
        'cooldown_bars_after_loss': 5,
        'duplicate_signal_expiry_bars': 10,
    }
    cfg = SignalQualityConfig()
    assert cfg.minimum_signal_score == pytest.approx(0.65)
    assert cfg.minimum_score_delta == pytest.approx(0.15)
    assert cfg.minimum_market_quality == pytest.approx(0.60)
    assert cfg.minimum_directional_confirmations == 3

def test_config_payload_without_signal_quality_uses_defaults() -> None:
    payload = valid_system_config_payload()
    payload.pop('signal_quality', None)
    assert 'signal_quality' not in payload
    config = parse_config_payload(payload)
    assert config.signal_quality.minimum_signal_score == pytest.approx(0.65)
    assert config.signal_quality.duplicate_signal_expiry_bars == 10

def test_invalid_config_rejects_out_of_range_score() -> None:
    with pytest.raises(ValidationError):
        SignalQualityConfig(minimum_signal_score=1.5)
    with pytest.raises(ValidationError):
        SignalQualityConfig(minimum_directional_confirmations=5)
    with pytest.raises(ValidationError):
        SignalQualityConfig(cooldown_bars_after_trade=5, cooldown_bars_after_loss=2)

def test_strong_signal_passes() -> None:
    result = evaluate_signal_quality(**_quality_kwargs())
    assert isinstance(result, SignalQualityResult)
    assert result.passed is True
    assert result.decision == Side.BUY.value
    assert result.reason_code is None
    assert result.fingerprint
    assert result.confirmation_count >= 3

def test_weak_winning_score_waits() -> None:
    result = evaluate_signal_quality(**_quality_kwargs(buy_score=0.50, sell_score=0.20, buy_components=_buy_components(strong=False)))
    assert result.passed is False
    assert result.decision == 'WAIT'
    assert result.reason_code == REASON_SIGNAL_SCORE_BELOW_MINIMUM

def test_score_delta_too_small_waits() -> None:
    result = evaluate_signal_quality(**_quality_kwargs(buy_score=0.80, sell_score=0.72, sell_components=_sell_components(weak=False)))
    assert result.passed is False
    assert result.reason_code == REASON_SIGNAL_DELTA_TOO_SMALL
    assert result.score_delta == pytest.approx(0.08)

def test_score_delta_too_small_when_opposite_invalid() -> None:
    result = evaluate_signal_quality(**_quality_kwargs(buy_score=0.68, sell_score=0.62, sell_valid=False, sell_components=_sell_components(weak=False)))
    assert result.passed is False
    assert result.reason_code == REASON_SIGNAL_DELTA_TOO_SMALL
    assert result.score_delta == pytest.approx(0.06)

def test_market_quality_too_low_waits() -> None:
    result = evaluate_signal_quality(**_quality_kwargs(market_quality_score=0.40))
    assert result.passed is False
    assert result.reason_code == REASON_MARKET_QUALITY_TOO_LOW

def test_insufficient_confirmations_waits() -> None:
    buy = {'momentum': 0.90, 'trend': 0.50, 'structure': 0.50, 'pressure': 0.50, 'behavior': 0.80, 'impact': 0.80, 'context': 0.80}
    sell = {'momentum': 0.40, 'trend': 0.51, 'structure': 0.51, 'pressure': 0.51, 'behavior': 0.80, 'impact': 0.80, 'context': 0.80}
    result = evaluate_signal_quality(**_quality_kwargs(buy_components=buy, sell_components=sell, buy_score=0.80, sell_score=0.40, signal_quality_config=_cfg(minimum_directional_confirmations=3)))
    assert result.passed is False
    assert result.reason_code == REASON_INSUFFICIENT_DIRECTIONAL_CONFIRMATIONS
    assert result.confirmation_count < 3

def test_cooldown_active_waits() -> None:
    result = evaluate_signal_quality(**_quality_kwargs(cooldown_bars_remaining=2, last_trade_result='loss'))
    assert result.passed is False
    assert result.reason_code == REASON_TRADE_COOLDOWN_ACTIVE
    assert result.cooldown_bars_remaining == 2

def test_duplicate_fingerprint_waits() -> None:
    fingerprint = build_signal_fingerprint(
        symbol='EURUSD',
        side=Side.BUY.value,
        candle_time_utc='2026-07-07T06:02:00.000Z',
        structure_level=1.10310,
        setup_type='directional',
        structure_id='legacy-test',
        setup_origin_timestamp='2026-07-07T06:00:00.000Z',
    )
    result = evaluate_signal_quality(**_quality_kwargs(active_fingerprints={fingerprint: '5'}, structure_level=1.10310, structure_id='legacy-test', setup_origin_timestamp='2026-07-07T06:00:00.000Z', setup_type='directional'))
    assert result.passed is False
    assert result.reason_code == REASON_DUPLICATE_SIGNAL
    assert result.fingerprint == fingerprint

def test_no_valid_setup_waits() -> None:
    result = evaluate_signal_quality(**_quality_kwargs(buy_valid=False, sell_valid=False, buy_score=0.0, sell_score=0.0))
    assert result.passed is False
    assert result.reason_code == REASON_NO_VALID_SETUP

def test_directional_and_market_quality_helpers() -> None:
    components = _buy_components()
    weights = {'momentum': 1.0, 'trend': 1.0, 'structure': 1.0, 'pressure': 1.0, 'behavior': 1.0, 'impact': 1.0, 'context': 1.0}
    directional = calculate_directional_score(components, weights)
    quality = calculate_market_quality_score(components)
    assert 0.0 <= directional <= 1.0
    assert quality == pytest.approx((0.75 + 0.75 + 0.75) / 3.0)
    confirmations = build_component_confirmations(buy_components=_buy_components(), sell_components=_sell_components())
    assert count_directional_confirmations(confirmations, Side.BUY.value) >= 3
