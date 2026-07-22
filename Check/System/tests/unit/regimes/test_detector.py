"""Regime detector tests."""

from __future__ import annotations

from tests.conftest import make_flat_range_m15, make_m15_series

from checktrader.config.loader import load_config
from checktrader.domain.enums import MarketRegime, ReasonCode
from checktrader.regimes.detector import RegimeDetector


def test_insufficient_history_is_unknown() -> None:
    cfg = load_config()
    det = RegimeDetector(cfg)
    bars = make_m15_series(50, drift=0.1)
    snap = det.update(bars)
    assert snap.regime is MarketRegime.UNKNOWN
    assert snap.reason is ReasonCode.HISTORY_INSUFFICIENT


def test_regime_sticky_until_new_m15() -> None:
    cfg = load_config()
    det = RegimeDetector(cfg)
    bars = make_m15_series(250, drift=0.08)
    first = det.update(bars)
    second = det.update(bars)
    assert first.regime == second.regime
    assert first.time == second.time


def test_strong_uptrend_path_runs() -> None:
    base = load_config()
    trend = base.regimes.trend.model_copy(
        update={
            "adx_min": 1.0,
            "adx_strong": 1.0,
            "ema20_slope_atr": 0.001,
            "ema50_slope_atr": 0.001,
        }
    )
    cfg = base.model_copy(update={"regimes": base.regimes.model_copy(update={"trend": trend})})
    det = RegimeDetector(cfg)
    bars = make_m15_series(280, start=50.0, drift=0.25, noise=0.01)
    snap = det.update(bars)
    assert snap.regime in {
        MarketRegime.TREND_UP,
        MarketRegime.TRANSITION,
        MarketRegime.RANGE,
        MarketRegime.UNKNOWN,
    }


def test_flat_series_not_trend_up_by_default() -> None:
    cfg = load_config()
    det = RegimeDetector(cfg)
    bars = make_flat_range_m15(250)
    snap = det.update(bars)
    assert snap.regime in {MarketRegime.RANGE, MarketRegime.TRANSITION, MarketRegime.UNKNOWN}
    assert snap.regime is not MarketRegime.TREND_UP
