"""Strategy router tests."""

from __future__ import annotations

from datetime import UTC, datetime

from checktrader.config.loader import load_config
from checktrader.domain.enums import Decision, MarketRegime, ReasonCode
from checktrader.domain.models import (
    AccountStatus,
    IndicatorSnapshot,
    MarketSnapshot,
    RegimeSnapshot,
    SymbolSpecs,
)
from checktrader.setups.repository import SetupRepository
from checktrader.strategies.base import StrategyContext
from checktrader.strategies.router import StrategyRouter


def _ctx(regime: MarketRegime, specs: SymbolSpecs) -> StrategyContext:
    cfg = load_config()
    ind = IndicatorSnapshot(datetime(2026, 1, 1, tzinfo=UTC), atr=0.5, adx=22.0)
    snap = RegimeSnapshot(regime, ind.time, ReasonCode.REGIME_TRANSITION, 0.0, ind)
    market = MarketSnapshot("TEST", 100.0, 100.1, ind.time)
    account = AccountStatus("1", 10000, 10000, 10000, "USD")
    return StrategyContext(cfg, specs, market, snap, account, [], SetupRepository())


def test_unknown_blocks_all(specs: SymbolSpecs) -> None:
    router = StrategyRouter()
    result = router.evaluate(_ctx(MarketRegime.UNKNOWN, specs))
    assert result.decision is Decision.HOLD
    assert result.reason is ReasonCode.REGIME_UNKNOWN


def test_transition_still_evaluates_breakout_then_trend(specs: SymbolSpecs) -> None:
    router = StrategyRouter()
    result = router.evaluate(_ctx(MarketRegime.TRANSITION, specs))
    assert result.decision is Decision.HOLD
    assert result.reason in {
        ReasonCode.REGIME_TRANSITION,
        ReasonCode.BREAKOUT_RETEST_PENDING,
        ReasonCode.BREAKOUT_BOX_PENDING,
        ReasonCode.NO_BREAKOUT_TRIGGER,
        ReasonCode.FALSE_BREAKOUT,
        ReasonCode.BREAKOUT_FILTERS_NOT_READY,
        ReasonCode.TREND_FILTERS_NOT_READY,
        ReasonCode.NO_STRATEGY_FOR_REGIME,
        ReasonCode.NO_TRADE,
        ReasonCode.TRIGGER_NOT_CONFIRMED,
    }
