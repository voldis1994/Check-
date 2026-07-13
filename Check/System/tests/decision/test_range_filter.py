from __future__ import annotations
from datetime import datetime, timezone
from engine.analysis.engine import run_analysis_engine
from engine.decision.buy import calculate_buy_candidate
from engine.decision.filters.news_filter import evaluate_news_filter
from engine.decision.filters.range_filter import evaluate_ranging_entry_filter
from engine.decision.filters.spread_filter import evaluate_spread_filter
from engine.decision.filters.volatility_filter import evaluate_volatility_filter
from engine.decision.sell import calculate_sell_candidate
from engine.core.instance import Instance
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.models import UniverseRecord
from engine.state.instance_state import InstanceState

def _bar(index: int, open_: float, high: float, low: float, close: float) -> NormalizedMarketBar:
    return NormalizedMarketBar(time_utc=datetime(2026, 7, 7, 6, index, tzinfo=timezone.utc), open=open_, high=high, low=low, close=close, volume=100.0, symbol='EURUSD', timeframe='M1', digits=5, point=1e-05, bar_index=index)

def _universe(*, regime: str='ranging') -> UniverseRecord:
    return UniverseRecord(schema_version='1.0.0', timestamp_utc='2026-07-07T06:00:00.000Z', session='LONDON', market_regime=regime, news_window_active=False)

def _instance_state() -> InstanceState:
    state = InstanceState(instance=Instance(account_id='12345', symbol='EURUSD', magic=100001))
    state.update_instrument(digits=5, point=1e-05, pip=0.0001)
    return state

def _passing_filters() -> tuple:
    return (evaluate_spread_filter(relative_spread=1.0, threshold=2.0), evaluate_volatility_filter(relative_volatility=1.0, threshold=2.5), evaluate_news_filter(_universe(), block_high_impact_news=True))

def _range_top_after_up_leg() -> tuple[NormalizedMarketBar, ...]:
    return (_bar(0, 1.1000, 1.1005, 1.0995, 1.1000), _bar(1, 1.1000, 1.1015, 1.0998, 1.1010), _bar(2, 1.1010, 1.1025, 1.1008, 1.1020), _bar(3, 1.1020, 1.1030, 1.1018, 1.1028), _bar(4, 1.1028, 1.1032, 1.1024, 1.1029))

def _range_bottom_after_down_leg() -> tuple[NormalizedMarketBar, ...]:
    return (_bar(0, 1.1030, 1.1035, 1.1028, 1.1030), _bar(1, 1.1030, 1.1032, 1.1018, 1.1020), _bar(2, 1.1020, 1.1022, 1.1008, 1.1010), _bar(3, 1.1010, 1.1012, 1.0998, 1.1000), _bar(4, 1.1000, 1.1002, 1.0994, 1.0996))

def test_ranging_filter_blocks_buy_near_range_top() -> None:
    bars = _range_top_after_up_leg()
    reason = evaluate_ranging_entry_filter(regime='ranging', market_bars=bars, side='buy', structure_lookback_bars=5, block_ranging_chase_entries=True, ranging_extreme_threshold=0.65, ranging_recent_momentum_bars=3)
    assert reason is not None
    assert 'range top' in reason

def test_ranging_filter_blocks_sell_near_range_bottom() -> None:
    bars = _range_bottom_after_down_leg()
    reason = evaluate_ranging_entry_filter(regime='ranging', market_bars=bars, side='sell', structure_lookback_bars=5, block_ranging_chase_entries=True, ranging_extreme_threshold=0.65, ranging_recent_momentum_bars=3)
    assert reason is not None
    assert 'range bottom' in reason

def test_ranging_filter_blocks_buy_when_recent_move_is_down() -> None:
    bars = (_bar(0, 1.1010, 1.1015, 1.1005, 1.1010), _bar(1, 1.1010, 1.1012, 1.1000, 1.1005), _bar(2, 1.1005, 1.1008, 1.0995, 1.0998), _bar(3, 1.0998, 1.1000, 1.0990, 1.0992), _bar(4, 1.0992, 1.0994, 1.0988, 1.0990))
    reason = evaluate_ranging_entry_filter(regime='ranging', market_bars=bars, side='buy', structure_lookback_bars=5, block_ranging_chase_entries=True, ranging_extreme_threshold=0.65, ranging_recent_momentum_bars=3)
    assert reason is not None
    assert 'recent move is down' in reason

def _range_top_with_sell_started() -> tuple[NormalizedMarketBar, ...]:
    return (_bar(0, 1.1000, 1.1005, 1.0995, 1.1000), _bar(1, 1.1000, 1.1015, 1.0998, 1.1010), _bar(2, 1.1010, 1.1025, 1.1008, 1.1020), _bar(3, 1.1020, 1.1032, 1.1018, 1.1030), _bar(4, 1.1030, 1.1032, 1.1024, 1.1026), _bar(5, 1.1026, 1.1028, 1.1020, 1.1022), _bar(6, 1.1022, 1.1024, 1.1016, 1.1018))

def test_ranging_filter_allows_sell_when_recent_move_is_down_at_range_top() -> None:
    bars = _range_top_with_sell_started()
    reason = evaluate_ranging_entry_filter(regime='ranging', market_bars=bars, side='sell', structure_lookback_bars=5, block_ranging_chase_entries=True, ranging_extreme_threshold=0.65, ranging_recent_momentum_bars=3)
    assert reason is None

def test_ranging_filter_is_disabled_for_trending_regime() -> None:
    bars = _range_top_after_up_leg()
    reason = evaluate_ranging_entry_filter(regime='trending', market_bars=bars, side='buy', structure_lookback_bars=5, block_ranging_chase_entries=True, ranging_extreme_threshold=0.65, ranging_recent_momentum_bars=3)
    assert reason is None

def test_buy_candidate_is_invalid_in_ranging_when_chasing_range_top() -> None:
    bars = _range_top_after_up_leg()
    analysis = run_analysis_engine(_universe(regime='ranging'), bars)
    spread_filter, volatility_filter, news_filter = _passing_filters()
    candidate = calculate_buy_candidate(analysis=analysis, market_bars=bars, spread_filter=spread_filter, volatility_filter=volatility_filter, news_filter=news_filter, instance_state=_instance_state(), weights={'momentum': 1.0, 'trend': 1.0, 'structure': 1.0, 'pressure': 1.0, 'behavior': 1.0, 'impact': 1.0, 'context': 1.0}, stop_loss_buffer=0.0002, reward_ratio=2.0, structure_lookback_bars=5, block_ranging_chase_entries=True, ranging_extreme_threshold=0.65, ranging_recent_momentum_bars=3)
    assert not candidate.valid
    assert candidate.invalid_reason is not None
    assert 'ranging' in candidate.invalid_reason

def test_sell_candidate_is_invalid_in_ranging_when_chasing_range_bottom() -> None:
    bars = _range_bottom_after_down_leg()
    analysis = run_analysis_engine(_universe(regime='ranging'), bars)
    spread_filter, volatility_filter, news_filter = _passing_filters()
    candidate = calculate_sell_candidate(analysis=analysis, market_bars=bars, spread_filter=spread_filter, volatility_filter=volatility_filter, news_filter=news_filter, instance_state=_instance_state(), weights={'momentum': 1.0, 'trend': 1.0, 'structure': 1.0, 'pressure': 1.0, 'behavior': 1.0, 'impact': 1.0, 'context': 1.0}, stop_loss_buffer=0.0002, reward_ratio=2.0, structure_lookback_bars=5, block_ranging_chase_entries=True, ranging_extreme_threshold=0.65, ranging_recent_momentum_bars=3)
    assert not candidate.valid
    assert candidate.invalid_reason is not None
    assert 'ranging' in candidate.invalid_reason
