"""Trend / range / breakout strategy smoke tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from checktrader.config.loader import load_config
from checktrader.domain.enums import Decision, MarketRegime, ReasonCode
from checktrader.domain.models import (
    AccountStatus,
    Candle,
    IndicatorSnapshot,
    MarketSnapshot,
    RegimeSnapshot,
    SymbolSpecs,
)
from checktrader.setups.repository import SetupRepository
from checktrader.strategies.base import StrategyContext
from checktrader.strategies.breakout import BreakoutStrategy
from checktrader.strategies.range_reversion import RangeReversionStrategy
from checktrader.strategies.trend_continuation import TrendContinuationStrategy


def _m1(n: int, start: float = 100.0, drift: float = 0.01) -> list[Candle]:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    out: list[Candle] = []
    p = start
    for i in range(n):
        c = p + drift
        out.append(Candle(t0 + timedelta(minutes=i), p, max(p, c) + 0.05, min(p, c) - 0.05, c, 1.0, "M1", True))
        p = c
    return out


def _ctx(regime: MarketRegime, specs: SymbolSpecs, m1: list[Candle] | None = None) -> StrategyContext:
    cfg = load_config()
    bars = m1 or _m1(40)
    # crude M5/M15 copies for smoke
    m5 = [Candle(b.time, b.open, b.high, b.low, b.close, b.volume, "M5", True) for b in bars[::5]]
    m15 = [Candle(b.time, b.open, b.high, b.low, b.close, b.volume, "M15", True) for b in bars[::15]]
    ind = IndicatorSnapshot(
        bars[-1].time, ema_fast=101.0, ema_slow=100.0, ema200=95.0, atr=0.5, adx=28.0, plus_di=30.0, minus_di=10.0
    )
    snap = RegimeSnapshot(regime, bars[-1].time, ReasonCode.REGIME_TREND_UP_CONFIRMED, 0.5, ind)
    market = MarketSnapshot("TEST", bars[-1].close, bars[-1].close + 0.01, bars[-1].time, bars, m5, m15)
    return StrategyContext(cfg, specs, market, snap, AccountStatus("1", 1e4, 1e4, 1e4, "USD"), [], SetupRepository())


def test_trend_wrong_regime_no_open(specs: SymbolSpecs) -> None:
    result = TrendContinuationStrategy().evaluate(_ctx(MarketRegime.RANGE, specs))
    assert result.decision is not Decision.OPEN


def test_range_middle_reason_or_hold(specs: SymbolSpecs) -> None:
    result = RangeReversionStrategy().evaluate(_ctx(MarketRegime.RANGE, specs, _m1(60, start=100.0, drift=0.0)))
    assert result.decision in {Decision.HOLD, Decision.SKIP, Decision.BLOCK}
    assert result.reason is not None


def test_breakout_unknown_data_hold(specs: SymbolSpecs) -> None:
    result = BreakoutStrategy().evaluate(_ctx(MarketRegime.TRANSITION, specs, _m1(5)))
    assert result.decision is Decision.HOLD
