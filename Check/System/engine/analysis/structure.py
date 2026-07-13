from __future__ import annotations
from dataclasses import dataclass
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.constants import StructureBias

@dataclass(frozen=True)
class StructureAnalysis:
    swing_high: float
    swing_low: float
    structure_bias: str
    break_of_structure: bool
    support_level: float
    resistance_level: float

def analyze_structure(bars: tuple[NormalizedMarketBar, ...]) -> StructureAnalysis:
    if not bars:
        return StructureAnalysis(swing_high=0.0, swing_low=0.0, structure_bias=StructureBias.NEUTRAL.value, break_of_structure=False, support_level=0.0, resistance_level=0.0)
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    closes = [bar.close for bar in bars]
    swing_high = max(highs)
    swing_low = min(lows)
    support = swing_low
    resistance = swing_high
    first_close = closes[0]
    last_close = closes[-1]
    if last_close > first_close:
        bias = StructureBias.BULLISH.value
    elif last_close < first_close:
        bias = StructureBias.BEARISH.value
    else:
        bias = StructureBias.NEUTRAL.value
    prior_high = max(highs[:-1]) if len(highs) > 1 else highs[0]
    prior_low = min(lows[:-1]) if len(lows) > 1 else lows[0]
    latest_close = closes[-1]
    bos = latest_close > prior_high or latest_close < prior_low
    return StructureAnalysis(swing_high=swing_high, swing_low=swing_low, structure_bias=bias, break_of_structure=bos, support_level=support, resistance_level=resistance)

def analyze_structure_window(bars: tuple[NormalizedMarketBar, ...], *, structure_lookback_bars: int) -> StructureAnalysis:
    if structure_lookback_bars <= 0:
        raise ValueError('structure_lookback_bars must be positive')
    if not bars:
        return analyze_structure(bars)
    window = bars[-structure_lookback_bars:] if len(bars) > structure_lookback_bars else bars
    return analyze_structure(window)
