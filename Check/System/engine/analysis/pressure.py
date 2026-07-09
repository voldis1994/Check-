from __future__ import annotations
from dataclasses import dataclass
from engine.normalizer.market_normalizer import NormalizedMarketBar

@dataclass(frozen=True)
class PressureAnalysis:
    buy_pressure: float
    sell_pressure: float
    pressure_delta: float
    absorption_detected: bool

def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))

def analyze_pressure(bars: tuple[NormalizedMarketBar, ...]) -> PressureAnalysis:
    if not bars:
        return PressureAnalysis(buy_pressure=0.5, sell_pressure=0.5, pressure_delta=0.0, absorption_detected=False)
    buy_components: list[float] = []
    sell_components: list[float] = []
    absorption_detected = False
    for bar in bars:
        bar_range = bar.high - bar.low
        if bar_range <= 0:
            buy_components.append(0.5)
            sell_components.append(0.5)
            continue
        body = bar.close - bar.open
        upper_wick = bar.high - max(bar.open, bar.close)
        lower_wick = min(bar.open, bar.close) - bar.low
        body_factor = _clamp(abs(body) / bar_range, 0.0, 1.0)
        if body >= 0:
            buy_value = 0.5 + 0.5 * body_factor
            sell_value = 1.0 - buy_value
        else:
            sell_value = 0.5 + 0.5 * body_factor
            buy_value = 1.0 - sell_value
        wick_balance = (lower_wick - upper_wick) / bar_range
        buy_value = _clamp(buy_value + 0.1 * wick_balance, 0.0, 1.0)
        sell_value = _clamp(sell_value - 0.1 * wick_balance, 0.0, 1.0)
        if abs(body) <= 0.2 * bar_range and upper_wick + lower_wick >= 0.7 * bar_range:
            absorption_detected = True
        buy_components.append(buy_value)
        sell_components.append(sell_value)
    buy_pressure = _clamp(sum(buy_components) / len(buy_components), 0.0, 1.0)
    sell_pressure = _clamp(sum(sell_components) / len(sell_components), 0.0, 1.0)
    pressure_delta = buy_pressure - sell_pressure
    return PressureAnalysis(buy_pressure=buy_pressure, sell_pressure=sell_pressure, pressure_delta=pressure_delta, absorption_detected=absorption_detected)
