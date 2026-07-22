"""Indicator unit tests — no look-ahead."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from checktrader.domain.models import Candle
from checktrader.market_data.indicators import atr, ema
from checktrader.market_data.swings import confirmed_swings


def _bars(n: int, start: float = 1.0, step: float = 0.01) -> list[Candle]:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    out: list[Candle] = []
    p = start
    for i in range(n):
        c = p + step
        out.append(Candle(t0 + timedelta(minutes=i), p, max(p, c) + 0.001, min(p, c) - 0.001, c, 1.0, "M1", True))
        p = c
    return out


def test_ema_no_lookahead_prefix_stable() -> None:
    bars = _bars(40)
    full = ema(bars, 10)
    prefix = ema(bars[:25], 10)
    assert full[24] == prefix[24]
    assert full[9] is not None
    assert all(v is None for v in full[:9])


def test_atr_requires_period() -> None:
    bars = _bars(20)
    vals = atr(bars, 14)
    assert all(v is None for v in vals[:13])
    assert vals[13] is not None


def test_swings_need_confirmation_bars() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    # Build a peak that is uniquely highest so confirmation is unambiguous
    prices = [1.0, 1.05, 1.10, 1.40, 1.10, 1.05, 1.00, 0.95, 0.90]
    bars = [
        Candle(t0 + timedelta(minutes=i), p, p + 0.001, p - 0.001, p, 1.0, "M15", True) for i, p in enumerate(prices)
    ]
    swings = confirmed_swings(bars, lookback=2)
    highs = [s for s in swings if s.price >= 1.40]
    assert highs
    assert highs[0].index == 3
    assert highs[0].confirmed_at == bars[5].time
