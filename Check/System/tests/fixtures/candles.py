"""Deterministic synthetic M1 candle helpers for strategy / market tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from checktrader.domain.market import Candle
from checktrader.market_data.aggregator import aggregate_timeframe, hma


def _ts(start: datetime, minute: int) -> str:
    moment = start + timedelta(minutes=minute)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_m1_candle(
    *,
    open_time_utc: str,
    open_: float,
    high: float,
    low: float,
    close: float,
    complete: bool = True,
    tick_volume: float = 100.0,
    spread: float = 2.0,
) -> Candle:
    open_dt = datetime.fromisoformat(open_time_utc.replace("Z", "+00:00"))
    close_dt = open_dt + timedelta(minutes=1)
    return Candle(
        open_time_utc=open_time_utc,
        close_time_utc=close_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        open=round(open_, 5),
        high=round(high, 5),
        low=round(low, 5),
        close=round(close, 5),
        tick_volume=tick_volume,
        spread=spread,
        complete=complete,
        timeframe="M1",
    )


def candle_dicts(candles: list[Candle]) -> list[dict[str, object]]:
    return [
        {
            "open_time_utc": c.open_time_utc,
            "close_time_utc": c.close_time_utc,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "tick_volume": c.tick_volume,
            "spread": c.spread,
            "complete": c.complete,
        }
        for c in candles
    ]


def _m1_from_htf_ohlc(
    start_dt: datetime, idx: int, minutes: int, o: float, h: float, low_v: float, c: float
) -> list[Candle]:
    """Expand one HTF candle into `minutes` M1 bars that aggregate back to OHLC."""
    points: list[float] = []
    for j in range(minutes):
        if j == 0:
            px = o
        elif j < max(minutes // 4, 1):
            px = o + (h - o) * (j / max(minutes // 4, 1))
        elif j == max(minutes // 4, 1):
            px = h
        elif j < (minutes * 2) // 3:
            px = h + (low_v - h) * ((j - max(minutes // 4, 1)) / max((minutes * 2) // 3 - max(minutes // 4, 1), 1))
        elif j == (minutes * 2) // 3:
            px = low_v
        elif j < minutes - 1:
            px = low_v + (c - low_v) * ((j - (minutes * 2) // 3) / max(minutes - 1 - (minutes * 2) // 3, 1))
        else:
            px = c
        points.append(px)

    high_j = max(minutes // 4, 1)
    low_j = (minutes * 2) // 3
    bars: list[Candle] = []
    for j, px in enumerate(points):
        t = _ts(start_dt, idx * minutes + j)
        bo = points[j - 1] if j else o
        bc = px
        bh = max(bo, bc)
        bl = min(bo, bc)
        if j == high_j:
            bh = h
        if j == low_j:
            bl = low_v
        bars.append(make_m1_candle(open_time_utc=t, open_=bo, high=bh, low=bl, close=bc))
    return bars


def _buy_m15_ohlc_series(n: int = 40) -> list[tuple[float, float, float, float]]:
    """Zig-zag M15 OHLC with lookback=2 swing highs/lows forming HH + HL."""
    series: list[tuple[float, float, float, float]] = []
    for i in range(n):
        cycle = i // 5
        pos = i % 5
        base_low = 1.10000 + cycle * 0.00040
        base_high = base_low + 0.00055
        if pos == 0:
            o = c = base_low + 0.00030
            h, low_v = base_low + 0.00038, base_low + 0.00022
        elif pos == 1:
            o = c = base_low + 0.00022
            h, low_v = base_low + 0.00028, base_low + 0.00016
        elif pos == 2:
            # swing low
            o, c = base_low + 0.00018, base_low + 0.00020
            h, low_v = base_low + 0.00024, base_low
        elif pos == 3:
            o = c = base_low + 0.00028
            h, low_v = base_low + 0.00035, base_low + 0.00020
        else:
            # swing high
            o, c = base_low + 0.00035, base_low + 0.00040
            h, low_v = base_high, base_low + 0.00030
        series.append((o, h, low_v, c))
    return series


def _sell_m15_ohlc_series(n: int = 40) -> list[tuple[float, float, float, float]]:
    """Zig-zag M15 OHLC with LH + LL for bearish bias."""
    series: list[tuple[float, float, float, float]] = []
    for i in range(n):
        cycle = i // 5
        pos = i % 5
        base_high = 1.12000 - cycle * 0.00040
        base_low = base_high - 0.00055
        if pos == 0:
            o = c = base_high - 0.00030
            h, low_v = base_high - 0.00022, base_high - 0.00038
        elif pos == 1:
            o = c = base_high - 0.00022
            h, low_v = base_high - 0.00016, base_high - 0.00028
        elif pos == 2:
            # swing high
            o, c = base_high - 0.00018, base_high - 0.00020
            h, low_v = base_high, base_high - 0.00024
        elif pos == 3:
            o = c = base_high - 0.00028
            h, low_v = base_high - 0.00020, base_high - 0.00035
        else:
            # swing low
            o, c = base_high - 0.00035, base_high - 0.00040
            h, low_v = base_high - 0.00030, base_low
        series.append((o, h, low_v, c))
    return series


def _structure_m1(series: list[tuple[float, float, float, float]], start_utc: str) -> list[Candle]:
    start_dt = datetime.fromisoformat(start_utc.replace("Z", "+00:00")).astimezone(UTC)
    bars: list[Candle] = []
    for i, (o, h, low_v, c) in enumerate(series):
        bars.extend(_m1_from_htf_ohlc(start_dt, i, 15, o, h, low_v, c))
    return bars


def _shape_pullback_m5(bars: list[Candle], *, side: str) -> list[Candle]:
    """Rewrite the last complete M5 (last 5 M1) into an HMA pullback."""
    m5 = aggregate_timeframe(bars, minutes=5, timeframe="M5")
    hma5 = hma([c.close for c in m5], 21)
    assert hma5 is not None
    out = list(bars)
    start = len(out) - 5
    base_t = out[start].open_time_utc
    for j in range(5):
        od = datetime.fromisoformat(base_t.replace("Z", "+00:00")) + timedelta(minutes=j)
        t = od.strftime("%Y-%m-%dT%H:%M:%SZ")
        if side == "BUY":
            o = hma5 + 0.00003 - j * 0.000008
            c = o - 0.000006
            hi = max(o, c) + 0.000015
            lo = hma5 - 0.00004
        else:
            o = hma5 - 0.00003 + j * 0.000008
            c = o + 0.000006
            hi = hma5 + 0.00004
            lo = min(o, c) - 0.000015
        out[start + j] = make_m1_candle(open_time_utc=t, open_=o, high=hi, low=lo, close=c)
    return out


def _append_trigger_m1(bars: list[Candle], *, side: str, buffer_price: float = 0.00005) -> list[Candle]:
    """
    Append one complete M1 beyond the last HTF bucket so aggregation keeps the
    pullback M5/M15 intact while M1 can break the prior trigger.
    """
    m5 = aggregate_timeframe(bars, minutes=5, timeframe="M5")
    prior = m5[-4:-1] if len(m5) >= 4 else m5[:-1]
    last = bars[-1]
    last_open = datetime.fromisoformat(last.open_time_utc.replace("Z", "+00:00"))
    t = (last_open + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if side == "BUY":
        trigger = max(c.high for c in prior)
        o = trigger - 0.00002
        c = trigger + buffer_price
        return bars + [make_m1_candle(open_time_utc=t, open_=o, high=c + 0.00002, low=o - 0.00002, close=c)]
    trigger = min(c.low for c in prior)
    o = trigger + 0.00002
    c = trigger - buffer_price
    return bars + [make_m1_candle(open_time_utc=t, open_=o, high=o + 0.00002, low=c - 0.00002, close=c)]


def synthesize_buy_setup_m1(
    *,
    m15_bars: int = 40,
    trigger: bool = True,
    start_utc: str = "2026-01-01T00:00:00Z",
) -> list[Candle]:
    bars = _structure_m1(_buy_m15_ohlc_series(m15_bars), start_utc)
    bars = _shape_pullback_m5(bars, side="BUY")
    if trigger:
        bars = _append_trigger_m1(bars, side="BUY")
    return bars


def synthesize_sell_setup_m1(
    *,
    m15_bars: int = 40,
    trigger: bool = True,
    start_utc: str = "2026-01-01T00:00:00Z",
) -> list[Candle]:
    bars = _structure_m1(_sell_m15_ohlc_series(m15_bars), start_utc)
    bars = _shape_pullback_m5(bars, side="SELL")
    if trigger:
        bars = _append_trigger_m1(bars, side="SELL")
    return bars


def synthesize_unclear_m1(*, n_bars: int = 600, start_utc: str = "2026-01-01T00:00:00Z") -> list[Candle]:
    start = datetime.fromisoformat(start_utc.replace("Z", "+00:00")).astimezone(UTC)
    out: list[Candle] = []
    price = 1.10000
    for i in range(n_bars):
        phase = 1 if (i // 10) % 2 == 0 else -1
        open_ = price
        close = price + phase * 0.00002
        high = max(open_, close) + 0.00008
        low = min(open_, close) - 0.00008
        out.append(
            make_m1_candle(
                open_time_utc=_ts(start, i),
                open_=open_,
                high=high,
                low=low,
                close=close,
            )
        )
        price = close
    return out


def sequential_m1(
    *,
    n: int,
    start_utc: str = "2026-03-01T10:00:00Z",
    start_price: float = 1.10000,
    complete: bool = True,
) -> list[Candle]:
    start = datetime.fromisoformat(start_utc.replace("Z", "+00:00")).astimezone(UTC)
    out: list[Candle] = []
    price = start_price
    for i in range(n):
        open_ = price
        close = price + 0.00001
        out.append(
            make_m1_candle(
                open_time_utc=_ts(start, i),
                open_=open_,
                high=close + 0.00002,
                low=open_ - 0.00002,
                close=close,
                complete=complete if i < n - 1 else complete,
            )
        )
        price = close
    return out


def with_incomplete_last(bars: list[Candle]) -> list[Candle]:
    if not bars:
        return bars
    last = bars[-1]
    return list(bars[:-1]) + [
        Candle(
            open_time_utc=last.open_time_utc,
            close_time_utc=last.close_time_utc,
            open=last.open,
            high=last.high,
            low=last.low,
            close=last.close,
            tick_volume=last.tick_volume,
            spread=last.spread,
            complete=False,
            timeframe=last.timeframe,
        )
    ]
