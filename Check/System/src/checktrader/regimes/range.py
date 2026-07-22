from __future__ import annotations

from checktrader.config.models import RegimeRangeConfig
from checktrader.domain.enums import MarketRegime, ReasonCode
from checktrader.domain.models import Candle, IndicatorSnapshot, RegimeSnapshot
from checktrader.market_data.bars import closed_bars
from checktrader.market_data.indicators import adx, atr, ema


def _count_touches(bars: list[Candle], level: float, tol: float, min_bars_between: int) -> int:
    """
    Count bars whose high or low is within `tol` of `level`,
    requiring at least `min_bars_between` bars between successive touches.
    """
    touches = 0
    last_idx = -(min_bars_between + 1)
    for i, b in enumerate(bars):
        if (abs(b.high - level) <= tol or abs(b.low - level) <= tol) and i - last_idx > min_bars_between:
            touches += 1
            last_idx = i
    return touches


def detect_range(candles: list[Candle], config: RegimeRangeConfig) -> RegimeSnapshot | None:
    """
    Section 5.3: RANGE detection.

    Conditions (all required):
      - ADX14 <= adx_max (18)
      - EMA50 slope over ema50_flat_lookback bars / ATR14 <= ema50_flat_atr (flat)
      - |EMA20 - EMA50| / ATR14 <= ema_sep_atr  (compressed)
      - Range (hi-lo) / ATR14 in [width_min_atr, width_max_atr]
      - >= min_touches_per_side touches on each side (spaced by min_bars_between_touches)
    """
    bars = closed_bars(candles)
    if len(bars) < config.range_lookback:
        return None

    e20 = ema(bars, config.ema20_period)
    e50 = ema(bars, config.ema50_period)
    av = atr(bars, config.atr_period)
    ax, p, m = adx(bars, config.adx_period)

    lf = e20[-1]
    ls = e50[-1]
    la = av[-1]
    ladx = ax[-1]

    if any(v is None for v in (lf, ls, la, ladx)):
        return None
    assert lf is not None and ls is not None and la is not None and ladx is not None
    lf_f, ls_f, la_f, ladx_f = float(lf), float(ls), float(la), float(ladx)
    if ladx_f > config.adx_max:
        return None

    sep = abs(lf_f - ls_f) / la_f
    if sep > config.ema_sep_atr:
        return None

    # EMA50 flatness: slope over ema50_flat_lookback bars / ATR
    flat_idx = len(bars) - config.ema50_flat_lookback - 1
    if flat_idx < 0 or e50[flat_idx] is None:
        return None
    e50_prev = float(e50[flat_idx])  # type: ignore[arg-type]
    e50_slope = abs(ls_f - e50_prev) / la_f
    if e50_slope > config.ema50_flat_atr:
        return None

    # Range boundaries from last range_lookback bars
    window = bars[-config.range_lookback :]
    hi = max(b.high for b in window)
    lo = min(b.low for b in window)
    width = hi - lo
    width_atr = width / la_f
    if width_atr < config.width_min_atr or width_atr > config.width_max_atr:
        return None

    tol = config.touch_tol_atr * la_f
    hi_touches = _count_touches(window, hi, tol, config.min_bars_between_touches)
    lo_touches = _count_touches(window, lo, tol, config.min_bars_between_touches)
    if hi_touches < config.min_touches_per_side or lo_touches < config.min_touches_per_side:
        return None

    lp = p[-1]
    lm = m[-1]
    meta = {
        "range_high": hi,
        "range_low": lo,
        "width_atr": width_atr,
        "ema_sep_atr": sep,
        "hi_touches": hi_touches,
        "lo_touches": lo_touches,
    }
    ind = IndicatorSnapshot(
        bars[-1].time,
        lf_f,
        ls_f,
        None,
        None,
        la_f,
        ladx_f,
        float(lp) if lp is not None else None,
        float(lm) if lm is not None else None,
        meta,
    )
    confidence = max(0.0, config.ema_sep_atr - sep)
    return RegimeSnapshot(MarketRegime.RANGE, bars[-1].time, ReasonCode.REGIME_RANGE_CONFIRMED, confidence, ind)
