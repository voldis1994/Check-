from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from engine.core.clock import format_utc_timestamp
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.constants import StructureBias, TIMEFRAME_M1


def normalize_price_level(level: float, *, digits: int) -> str:
    """Normalize a price to instrument digits for stable identity strings."""
    safe_digits = max(0, int(digits))
    return f'{round(float(level), safe_digits):.{safe_digits}f}'


def build_structure_id(
    *,
    structure_bias: str,
    break_of_structure: bool,
    swing_high: float,
    swing_low: float,
    breakout_level: float,
    setup_origin_timestamp: str,
    digits: int,
) -> str:
    """Deterministic structure identity (SHA-256), stable across processes."""
    payload = '|'.join(
        (
            structure_bias,
            '1' if break_of_structure else '0',
            normalize_price_level(swing_high, digits=digits),
            normalize_price_level(swing_low, digits=digits),
            normalize_price_level(breakout_level, digits=digits),
            setup_origin_timestamp,
            TIMEFRAME_M1,
        )
    )
    return sha256(payload.encode('utf-8')).hexdigest()[:24]


@dataclass(frozen=True)
class StructureAnalysis:
    swing_high: float
    swing_low: float
    structure_bias: str
    break_of_structure: bool
    support_level: float
    resistance_level: float
    structure_id: str = ''
    setup_origin_timestamp: str = ''
    swing_high_time_utc: str = ''
    swing_low_time_utc: str = ''
    breakout_level: float = 0.0

    def structure_level_for_side(self, side: str) -> float:
        """Anchor level for setup identity (not the moving entry/close price)."""
        side_upper = side.upper()
        if side_upper == 'BUY':
            return float(self.support_level if self.support_level else self.swing_low)
        if side_upper == 'SELL':
            return float(self.resistance_level if self.resistance_level else self.swing_high)
        return float(self.breakout_level or self.swing_low)

    def origin_timestamp_for_side(self, side: str) -> str:
        side_upper = side.upper()
        if side_upper == 'BUY' and self.swing_low_time_utc:
            return self.swing_low_time_utc
        if side_upper == 'SELL' and self.swing_high_time_utc:
            return self.swing_high_time_utc
        return self.setup_origin_timestamp


def _empty_structure() -> StructureAnalysis:
    return StructureAnalysis(
        swing_high=0.0,
        swing_low=0.0,
        structure_bias=StructureBias.NEUTRAL.value,
        break_of_structure=False,
        support_level=0.0,
        resistance_level=0.0,
        structure_id='',
        setup_origin_timestamp='',
        swing_high_time_utc='',
        swing_low_time_utc='',
        breakout_level=0.0,
    )


def analyze_structure(bars: tuple[NormalizedMarketBar, ...]) -> StructureAnalysis:
    if not bars:
        return _empty_structure()
    digits = int(bars[-1].digits)
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    closes = [bar.close for bar in bars]
    swing_high = max(highs)
    swing_low = min(lows)
    swing_high_index = highs.index(swing_high)
    swing_low_index = lows.index(swing_low)
    swing_high_time = format_utc_timestamp(bars[swing_high_index].time_utc)
    swing_low_time = format_utc_timestamp(bars[swing_low_index].time_utc)
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
    bos_up = latest_close > prior_high
    bos_down = latest_close < prior_low
    bos = bos_up or bos_down
    if bos_up:
        breakout_level = float(prior_high)
    elif bos_down:
        breakout_level = float(prior_low)
    else:
        breakout_level = float(prior_high if bias == StructureBias.BULLISH.value else prior_low)
    # Origin: bar that formed the structural anchor for the current bias.
    if bias == StructureBias.BULLISH.value:
        setup_origin = swing_low_time
    elif bias == StructureBias.BEARISH.value:
        setup_origin = swing_high_time
    else:
        setup_origin = swing_low_time if swing_low_index <= swing_high_index else swing_high_time
    structure_id = build_structure_id(
        structure_bias=bias,
        break_of_structure=bos,
        swing_high=swing_high,
        swing_low=swing_low,
        breakout_level=breakout_level,
        setup_origin_timestamp=setup_origin,
        digits=digits,
    )
    return StructureAnalysis(
        swing_high=swing_high,
        swing_low=swing_low,
        structure_bias=bias,
        break_of_structure=bos,
        support_level=support,
        resistance_level=resistance,
        structure_id=structure_id,
        setup_origin_timestamp=setup_origin,
        swing_high_time_utc=swing_high_time,
        swing_low_time_utc=swing_low_time,
        breakout_level=breakout_level,
    )


def analyze_structure_window(bars: tuple[NormalizedMarketBar, ...], *, structure_lookback_bars: int) -> StructureAnalysis:
    if structure_lookback_bars <= 0:
        raise ValueError('structure_lookback_bars must be positive')
    if not bars:
        return analyze_structure(bars)
    window = bars[-structure_lookback_bars:] if len(bars) > structure_lookback_bars else bars
    return analyze_structure(window)


def derive_setup_type(*, side: str, structure: StructureAnalysis) -> str:
    """Label the setup family for fingerprinting (not a separate strategy)."""
    side_upper = side.upper()
    bias = structure.structure_bias
    if structure.break_of_structure:
        if side_upper == 'BUY':
            return 'bos_buy'
        if side_upper == 'SELL':
            return 'bos_sell'
    if side_upper == 'BUY' and bias == StructureBias.BULLISH.value:
        return 'continuation_buy'
    if side_upper == 'SELL' and bias == StructureBias.BEARISH.value:
        return 'continuation_sell'
    if side_upper == 'BUY':
        return 'directional_buy'
    if side_upper == 'SELL':
        return 'directional_sell'
    return 'directional'
