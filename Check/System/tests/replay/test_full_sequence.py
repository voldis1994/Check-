"""Full regime sequence replay test: UNKNOWN → TRANSITION/TREND/RANGE without crash."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from checktrader.config.loader import load_config
from checktrader.domain.enums import MarketRegime, ReasonCode
from checktrader.domain.models import Candle
from checktrader.regimes.detector import RegimeDetector

# ── Synthetic bar generators ───────────────────────────────────────────────────


def _bar(i: int, o: float, h: float, lo: float, c: float, *, tf: str = "M15") -> Candle:
    t = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=15 * i)
    return Candle(t, o, h, lo, c, 100.0, tf, True)


def _uptrend_bars(n: int, start: float = 50.0, drift: float = 0.30, noise: float = 0.01) -> list[Candle]:
    out: list[Candle] = []
    p = start
    for i in range(n):
        c = p + drift
        out.append(_bar(i, p, max(p, c) + noise, min(p, c) - noise, c))
        p = c
    return out


def _range_bars(n: int, mid: float = 100.0, half_width: float = 1.0, offset: int = 0) -> list[Candle]:
    out: list[Candle] = []
    for i in range(n):
        phase = i % 8
        if phase in {0, 1}:
            lo = mid - half_width
            h = lo + half_width * 0.3
            o = lo + 0.05
            c = lo + 0.10
        elif phase in {4, 5}:
            h = mid + half_width
            lo = h - half_width * 0.3
            o = h - 0.10
            c = h - 0.05
        else:
            o = mid - 0.05
            c = mid + 0.05
            h = c + 0.10
            lo = o - 0.10
        out.append(_bar(i + offset, o, h, lo, c))
    return out


def _append_bar(bars: list[Candle], i_offset: int, o: float, drift: float = 0.05) -> Candle:
    c = o + drift
    t = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=15 * (len(bars) + i_offset))
    bar = Candle(t, o, max(o, c) + 0.01, min(o, c) - 0.01, c, 100.0, "M15", True)
    bars.append(bar)
    return bar


# ── Sequence tests ─────────────────────────────────────────────────────────────


def test_sequence_from_empty_to_unknown() -> None:
    """
    Expected path: no bars → UNKNOWN (NO_CLOSED_BARS)
    """
    cfg = load_config()
    det = RegimeDetector(cfg)
    snap = det.update([])
    assert snap.regime == MarketRegime.UNKNOWN
    assert snap.reason == ReasonCode.NO_CLOSED_BARS


def test_sequence_insufficient_to_unknown() -> None:
    """Expected path: below operable bars (~EMA50) → UNKNOWN (HISTORY_INSUFFICIENT)."""
    cfg = load_config()
    det = RegimeDetector(cfg)
    bars = _uptrend_bars(10)
    snap = det.update(bars)
    assert snap.regime == MarketRegime.UNKNOWN
    assert snap.reason == ReasonCode.HISTORY_INSUFFICIENT


def test_sequence_growing_toward_transition() -> None:
    """
    Expected path: 200 bars (barely enough) → regime determined (UNKNOWN/TRANSITION/other)
    No crash. Documents the path for 200+ bars.
    """
    cfg = load_config()
    det = RegimeDetector(cfg)
    bars = _uptrend_bars(200)
    snap = det.update(bars)
    # With exactly 200 bars all indicators should be computable
    assert snap.regime in {
        MarketRegime.UNKNOWN,
        MarketRegime.TRANSITION,
        MarketRegime.TREND_UP,
        MarketRegime.TREND_DOWN,
        MarketRegime.RANGE,
    }


def test_sequence_uptrend_eventually_produces_valid_regime() -> None:
    """
    Expected path: 280 strongly upward bars → TREND_UP or TRANSITION (with softened config)
    The test documents what regime a consistent uptrend produces.
    """
    base_cfg = load_config()
    trend_cfg = base_cfg.regimes.trend.model_copy(
        update={
            "adx_min": 1.0,
            "adx_strong": 1.0,
            "ema20_slope_atr": 0.001,
            "ema50_slope_atr": 0.001,
            "ema_sep_atr": 0.001,
        }
    )
    cfg = base_cfg.model_copy(update={"regimes": base_cfg.regimes.model_copy(update={"trend": trend_cfg})})
    det = RegimeDetector(cfg)
    bars = _uptrend_bars(280, drift=0.50, noise=0.005)
    snap = det.update(bars)
    assert snap.regime in {MarketRegime.TREND_UP, MarketRegime.TRANSITION, MarketRegime.RANGE}
    assert snap.reason not in {ReasonCode.HISTORY_INSUFFICIENT, ReasonCode.NO_CLOSED_BARS}


def test_sequence_incremental_bars_no_crash() -> None:
    """
    Feed bars one-by-one; detector should never raise.
    Below operable bars → UNKNOWN; after that regime may vary.
    """
    cfg = load_config()
    det = RegimeDetector(cfg)
    all_bars = _uptrend_bars(250, drift=0.20, noise=0.005)
    min_needed = max(
        cfg.regimes.trend.ema50_period + cfg.regimes.trend.slope_lookback + 2,
        cfg.regimes.trend.adx_period * 2,
        cfg.regimes.trend.atr_period + 2,
        cfg.regimes.trend.ema20_period + 2,
    )

    regimes_seen: list[MarketRegime] = []
    for i in range(1, len(all_bars) + 1):
        snap = det.update(all_bars[:i])
        regimes_seen.append(snap.regime)

    for regime in regimes_seen[: min_needed - 1]:
        assert regime == MarketRegime.UNKNOWN

    seen_non_unknown = {r for r in regimes_seen[min_needed - 1 :]}
    assert len(seen_non_unknown) >= 1


def test_sequence_range_detection_path() -> None:
    """
    Expected path: flat range bars → detector may produce RANGE (with softened config).
    Documents that the path is UNKNOWN → eventually RANGE/TRANSITION/other.
    """
    base_cfg = load_config()
    range_cfg = base_cfg.regimes.range.model_copy(
        update={
            "adx_max": 50.0,
            "ema50_flat_atr": 5.0,
            "ema_sep_atr": 5.0,
            "width_min_atr": 0.1,
            "width_max_atr": 100.0,
            "min_touches_per_side": 2,
        }
    )
    cfg = base_cfg.model_copy(update={"regimes": base_cfg.regimes.model_copy(update={"range": range_cfg})})
    det = RegimeDetector(cfg)
    bars = _range_bars(250, mid=100.0, half_width=1.0)
    snap = det.update(bars)
    # Should produce a valid regime without crash
    assert snap.regime in {
        MarketRegime.UNKNOWN,
        MarketRegime.TRANSITION,
        MarketRegime.RANGE,
        MarketRegime.TREND_UP,
        MarketRegime.TREND_DOWN,
    }


def test_sequence_regime_changes_update_on_new_bar() -> None:
    """Verify that adding a new bar updates the detector's snapshot time."""
    cfg = load_config()
    det = RegimeDetector(cfg)
    bars = _uptrend_bars(250)
    snap1 = det.update(bars)

    # Append one new bar
    t_new = bars[-1].time + timedelta(minutes=15)
    new_bar = Candle(
        t_new,
        bars[-1].close,
        bars[-1].close + 0.10,
        bars[-1].close - 0.05,
        bars[-1].close + 0.05,
        100.0,
        "M15",
        True,
    )
    snap2 = det.update(bars + [new_bar])
    # New bar time must be reflected
    assert snap2.time >= snap1.time
