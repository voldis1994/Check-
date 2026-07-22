"""TREND_UP / TREND_DOWN detection — sections 5.1 / 5.2."""

from __future__ import annotations

from checktrader.config.models import RegimeTrendConfig
from checktrader.domain.enums import MarketRegime, ReasonCode, Side
from checktrader.domain.models import Candle, IndicatorSnapshot, RegimeSnapshot
from checktrader.market_data.bars import closed_bars
from checktrader.market_data.indicators import adx, atr, ema
from checktrader.market_data.swings import confirmed_swings


def _indicator_snapshot(
    bars: list[Candle],
    *,
    lf: float,
    ls: float,
    l200: float,
    la: float,
    ladx: float,
    lp: float | None,
    lm: float | None,
    meta: dict[str, float],
) -> IndicatorSnapshot:
    return IndicatorSnapshot(bars[-1].time, lf, ls, l200, None, la, ladx, lp, lm, meta)


def _swing_structure_ok(bars: list[Candle], *, bullish: bool) -> bool:
    swings = confirmed_swings(bars, lookback=2)
    highs = [s for s in swings if s.side is Side.SELL]
    lows = [s for s in swings if s.side is Side.BUY]
    if len(highs) < 2 or len(lows) < 2:
        return False
    if bullish:
        return highs[-1].price > highs[-2].price and lows[-1].price > lows[-2].price
    return highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price


def detect_trend(candles: list[Candle], config: RegimeTrendConfig) -> RegimeSnapshot | None:
    bars = closed_bars(candles)
    if not bars:
        return None

    e20 = ema(bars, config.ema20_period)
    e50 = ema(bars, config.ema50_period)
    e200 = ema(bars, config.ema200_period)
    av = atr(bars, config.atr_period)
    ax, plus_di, minus_di = adx(bars, config.adx_period)

    raw = (e20[-1], e50[-1], e200[-1], av[-1], ax[-1], plus_di[-1], minus_di[-1])
    if any(v is None for v in raw):
        return None
    lf, ls, l200, la, ladx, lp, lm = (float(v) for v in raw)  # type: ignore[arg-type]

    close = bars[-1].close
    if la <= 0:
        return None

    slope_idx = len(bars) - config.slope_lookback - 1
    if slope_idx < 0 or e20[slope_idx] is None or e50[slope_idx] is None:
        return None
    e20_prev = float(e20[slope_idx])  # type: ignore[arg-type]
    e50_prev = float(e50[slope_idx])  # type: ignore[arg-type]
    slope20 = (lf - e20_prev) / la
    slope50 = (ls - e50_prev) / la

    up_indicators = (
        close > l200
        and lf > ls > l200
        and lf > e20_prev
        and ls > e50_prev
        and slope20 >= config.ema20_slope_atr
        and slope50 >= config.ema50_slope_atr
        and ladx >= config.adx_min
        and lp > lm
    )
    if up_indicators and (_swing_structure_ok(bars, bullish=True) or ladx >= config.adx_strong):
        meta = {"ema200": l200, "adx": ladx, "slope20": slope20, "slope50": slope50}
        ind = _indicator_snapshot(bars, lf=lf, ls=ls, l200=l200, la=la, ladx=ladx, lp=lp, lm=lm, meta=meta)
        return RegimeSnapshot(
            MarketRegime.TREND_UP,
            bars[-1].time,
            ReasonCode.REGIME_TREND_UP_CONFIRMED,
            abs(lf - ls) / la,
            ind,
        )

    dn_indicators = (
        close < l200
        and lf < ls < l200
        and lf < e20_prev
        and ls < e50_prev
        and slope20 <= -config.ema20_slope_atr
        and slope50 <= -config.ema50_slope_atr
        and ladx >= config.adx_min
        and lm > lp
    )
    if dn_indicators and (_swing_structure_ok(bars, bullish=False) or ladx >= config.adx_strong):
        meta = {"ema200": l200, "adx": ladx, "slope20": slope20, "slope50": slope50}
        ind = _indicator_snapshot(bars, lf=lf, ls=ls, l200=l200, la=la, ladx=ladx, lp=lp, lm=lm, meta=meta)
        return RegimeSnapshot(
            MarketRegime.TREND_DOWN,
            bars[-1].time,
            ReasonCode.REGIME_TREND_DOWN_CONFIRMED,
            abs(lf - ls) / la,
            ind,
        )

    return None
