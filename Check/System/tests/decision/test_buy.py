from __future__ import annotations
import inspect
from datetime import datetime, timezone
from engine.analysis.context import with_spread_filter_passed
from engine.analysis.engine import run_analysis_engine, with_analysis_context
from engine.core.instance import Instance
from engine.decision.buy import BuyCandidate, build_buy_component_scores, calculate_buy_candidate, calculate_buy_score
from engine.decision.filters.news_filter import evaluate_news_filter
from engine.decision.filters.spread_filter import evaluate_spread_filter
from engine.decision.filters.volatility_filter import evaluate_volatility_filter
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.models import UniverseRecord
from engine.state.instance_state import InstanceState

def _bar(index: int, open_: float, high: float, low: float, close: float) -> NormalizedMarketBar:
    return NormalizedMarketBar(time_utc=datetime(2026, 7, 7, 6, index, tzinfo=timezone.utc), open=open_, high=high, low=low, close=close, volume=100.0, symbol='EURUSD', timeframe='M1', digits=5, point=1e-05, bar_index=index)

def _universe() -> UniverseRecord:
    return UniverseRecord(schema_version='1.0.0', timestamp_utc='2026-07-07T06:00:00.000Z', session='LONDON', market_regime='trending', news_window_active=False)

def _bullish_bars() -> tuple[NormalizedMarketBar, ...]:
    return (_bar(0, 1.1, 1.102, 1.099, 1.1015), _bar(1, 1.1015, 1.103, 1.1005, 1.1022), _bar(2, 1.1022, 1.104, 1.101, 1.1031))

def _weights() -> dict[str, float]:
    return {'momentum': 1.0, 'trend': 1.0, 'structure': 1.0, 'pressure': 1.0, 'behavior': 1.0, 'impact': 1.0, 'context': 1.0}

def _instance_state() -> InstanceState:
    state = InstanceState(instance=Instance(account_id='12345', symbol='EURUSD', magic=100001))
    state.update_instrument(digits=5, point=1e-05, pip=0.0001)
    return state

def _passing_filters() -> tuple:
    return (evaluate_spread_filter(relative_spread=1.0, threshold=1.5), evaluate_volatility_filter(relative_volatility=1.0, threshold=1.5), evaluate_news_filter(_universe(), block_high_impact_news=True))

def _analysis_with_spread_filter(analysis, spread_filter):
    return with_analysis_context(analysis, with_spread_filter_passed(analysis.context, spread_filter.spread_acceptable))

def test_build_buy_component_scores_contains_all_components() -> None:
    analysis = run_analysis_engine(_universe(), _bullish_bars())
    scores = build_buy_component_scores(analysis)
    assert set(scores) == {'momentum', 'trend', 'structure', 'pressure', 'behavior', 'impact', 'context'}
    assert all((0.0 <= value <= 1.0 for value in scores.values()))

def test_calculate_buy_score_uses_weighted_average() -> None:
    component_scores = {'momentum': 1.0, 'trend': 0.0, 'structure': 0.0, 'pressure': 0.0, 'behavior': 0.0, 'impact': 0.0, 'context': 0.0}
    weights = {key: 0.0 for key in component_scores}
    weights['momentum'] = 1.0
    buy_score = calculate_buy_score(component_scores, weights)
    assert buy_score == 1.0

def test_valid_buy_candidate_contains_all_fields() -> None:
    bars = _bullish_bars()
    analysis = run_analysis_engine(_universe(), bars)
    spread_filter, volatility_filter, news_filter = _passing_filters()
    candidate = calculate_buy_candidate(analysis=_analysis_with_spread_filter(analysis, spread_filter), market_bars=bars, spread_filter=spread_filter, volatility_filter=volatility_filter, news_filter=news_filter, instance_state=_instance_state(), weights=_weights(), stop_loss_buffer=0.0002, reward_ratio=2.0, structure_lookback_bars=3, block_ranging_chase_entries=False, ranging_extreme_threshold=0.65, ranging_recent_momentum_bars=3)
    assert candidate.valid
    assert candidate.invalid_reason is None
    assert candidate.entry_price > 0
    assert candidate.stop_loss < candidate.entry_price
    assert candidate.take_profit > candidate.entry_price
    assert set(candidate.component_scores) == set(_weights())
    assert 0.0 <= candidate.buy_score <= 1.0

def test_invalid_buy_candidate_requires_invalid_reason() -> None:
    bars = _bullish_bars()
    analysis = run_analysis_engine(_universe(), bars)
    spread_filter, volatility_filter, _ = _passing_filters()
    spread_filter = evaluate_spread_filter(relative_spread=2.0, threshold=1.5)
    candidate = calculate_buy_candidate(analysis=_analysis_with_spread_filter(analysis, spread_filter), market_bars=bars, spread_filter=spread_filter, volatility_filter=volatility_filter, news_filter=evaluate_news_filter(_universe(), block_high_impact_news=True), instance_state=_instance_state(), weights=_weights(), stop_loss_buffer=0.0002, reward_ratio=2.0, structure_lookback_bars=3, block_ranging_chase_entries=False, ranging_extreme_threshold=0.65, ranging_recent_momentum_bars=3)
    assert isinstance(candidate, BuyCandidate)
    assert not candidate.valid
    assert candidate.invalid_reason is not None
    assert 'SPREAD_ABNORMAL' in candidate.invalid_reason

def test_buy_calculation_does_not_invoke_sell_logic() -> None:
    source = inspect.getsource(calculate_buy_candidate)
    assert 'sell' not in source.lower()
    assert 'engine.decision.sell' not in source
