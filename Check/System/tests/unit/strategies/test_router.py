"""Strategy router tests."""

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
from checktrader.strategies.router import StrategyRouter


def _ctx(regime: MarketRegime, specs: SymbolSpecs, *, with_m1: bool = False) -> StrategyContext:
    cfg = load_config()
    ind = IndicatorSnapshot(datetime(2026, 1, 1, tzinfo=UTC), atr=0.5, adx=22.0)
    snap = RegimeSnapshot(regime, ind.time, ReasonCode.REGIME_TRANSITION, 0.0, ind)
    m1: list[Candle] = []
    if with_m1:
        t0 = datetime(2026, 7, 22, 18, 0, tzinfo=UTC)
        for i in range(5):
            p = 2.90 + i * 0.001
            m1.append(Candle(t0 + timedelta(minutes=i), p, p + 0.002, p - 0.001, p + 0.001, 1.0, "M1", True))
    market = MarketSnapshot("TEST", 100.0, 100.1, ind.time, m1=m1)
    account = AccountStatus("1", 10000, 10000, 10000, "USD")
    return StrategyContext(cfg, specs, market, snap, account, [], SetupRepository())


def test_unknown_without_m1_holds(specs: SymbolSpecs) -> None:
    router = StrategyRouter()
    result = router.evaluate(_ctx(MarketRegime.UNKNOWN, specs, with_m1=False))
    assert result.decision is Decision.HOLD


def test_transition_with_m1_force_opens(specs: SymbolSpecs) -> None:
    router = StrategyRouter()
    result = router.evaluate(_ctx(MarketRegime.TRANSITION, specs, with_m1=True))
    assert result.decision is Decision.OPEN
    assert result.reason in {
        ReasonCode.FORCE_MOMENTUM_BUY,
        ReasonCode.FORCE_MOMENTUM_SELL,
        ReasonCode.BREAKOUT_BUY_SIGNAL,
        ReasonCode.BREAKOUT_SELL_SIGNAL,
        ReasonCode.TREND_BUY_SIGNAL,
        ReasonCode.TREND_SELL_SIGNAL,
    }
