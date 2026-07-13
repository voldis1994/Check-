from __future__ import annotations
from engine.analysis.structure import analyze_structure_window
from engine.decision.reason import build_reason
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.constants import MarketRegime, REASON_DATA_INVALID

def calculate_range_position(*, market_bars: tuple[NormalizedMarketBar, ...], structure_lookback_bars: int) -> float | None:
    if not market_bars:
        return None
    structure = analyze_structure_window(market_bars, structure_lookback_bars=structure_lookback_bars)
    range_height = structure.swing_high - structure.swing_low
    if range_height <= 0:
        return None
    close = market_bars[-1].close
    return (close - structure.swing_low) / range_height

def calculate_recent_price_delta(*, market_bars: tuple[NormalizedMarketBar, ...], recent_bars: int) -> float:
    if not market_bars:
        return 0.0
    window = market_bars[-recent_bars:] if len(market_bars) > recent_bars else market_bars
    if len(window) < 2:
        return 0.0
    return window[-1].close - window[0].close

def evaluate_ranging_entry_filter(*, regime: str, market_bars: tuple[NormalizedMarketBar, ...], side: str, structure_lookback_bars: int, block_ranging_chase_entries: bool, ranging_extreme_threshold: float, ranging_recent_momentum_bars: int) -> str | None:
    if not block_ranging_chase_entries:
        return None
    if regime != MarketRegime.RANGING.value:
        return None
    range_position = calculate_range_position(market_bars=market_bars, structure_lookback_bars=structure_lookback_bars)
    if range_position is None:
        return build_reason(REASON_DATA_INVALID, f'ranging: {side} blocked because structure range is flat')
    recent_delta = calculate_recent_price_delta(market_bars=market_bars, recent_bars=ranging_recent_momentum_bars)
    lower_bound = 1.0 - ranging_extreme_threshold
    if side == 'buy':
        if range_position > ranging_extreme_threshold:
            return build_reason(REASON_DATA_INVALID, 'ranging: buy blocked near range top after up-leg', range_position=range_position, threshold=ranging_extreme_threshold)
        if recent_delta < 0:
            return build_reason(REASON_DATA_INVALID, 'ranging: buy blocked while recent move is down', recent_delta=recent_delta)
        return None
    if range_position < lower_bound:
        return build_reason(REASON_DATA_INVALID, 'ranging: sell blocked near range bottom after down-leg', range_position=range_position, threshold=lower_bound)
    if recent_delta > 0:
        return build_reason(REASON_DATA_INVALID, 'ranging: sell blocked while recent move is up', recent_delta=recent_delta)
    return None
