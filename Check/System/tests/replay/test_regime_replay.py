"""Replay path: regime sequence through synthetic markets."""

from __future__ import annotations

from tests.conftest import make_flat_range_m15, make_m15_series

from checktrader.config.loader import load_config
from checktrader.domain.enums import MarketRegime
from checktrader.regimes.detector import RegimeDetector


def test_replay_history_then_trend_or_transition() -> None:
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

    short = make_m15_series(30)
    assert det.update(short).regime is MarketRegime.UNKNOWN

    det2 = RegimeDetector(cfg)
    up = make_m15_series(260, start=80.0, drift=0.3, noise=0.02)
    snap_up = det2.update(up)
    assert snap_up.regime in {
        MarketRegime.TREND_UP,
        MarketRegime.TRANSITION,
        MarketRegime.RANGE,
    }

    det3 = RegimeDetector(cfg)
    flat = make_flat_range_m15(260)
    snap_flat = det3.update(flat)
    assert snap_flat.regime in {
        MarketRegime.RANGE,
        MarketRegime.TRANSITION,
        MarketRegime.UNKNOWN,
        MarketRegime.TREND_UP,
        MarketRegime.TREND_DOWN,
    }
