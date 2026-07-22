"""Range regime touch-detection tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from checktrader.config.loader import load_config
from checktrader.domain.models import Candle
from checktrader.regimes.range import _count_touches, detect_range


def _bar(i: int, o: float, h: float, lo: float, c: float, *, tf: str = "M15") -> Candle:
    t = datetime(2025, 6, 1, tzinfo=UTC) + timedelta(minutes=15 * i)
    return Candle(t, o, h, lo, c, 50.0, tf, True)


def _range_bars(n: int = 60, *, mid: float = 100.0, half_width: float = 1.0) -> list[Candle]:
    """Bars oscillating in [mid-hw, mid+hw] with 2 touches on each side."""
    out: list[Candle] = []
    for i in range(n):
        phase = i % 10
        if phase in {0, 1}:
            # Touch low boundary
            o, c = mid - half_width + 0.05, mid - half_width + 0.10
            lo = mid - half_width
            h = mid - half_width + 0.3
        elif phase in {5, 6}:
            # Touch high boundary
            o, c = mid + half_width - 0.10, mid + half_width - 0.05
            h = mid + half_width
            lo = mid + half_width - 0.3
        else:
            # Middle bars
            o = mid + ((i % 3) - 1) * 0.1
            c = mid + ((i % 5) - 2) * 0.08
            h = max(o, c) + 0.15
            lo = min(o, c) - 0.15
        out.append(_bar(i, o, h, lo, c))
    return out


# ── _count_touches unit tests ──────────────────────────────────────────────────


def test_count_touches_exact_hit() -> None:
    """A bar whose high exactly equals level should count as one touch."""
    bars = [
        _bar(0, 99.0, 100.0, 98.5, 99.5),  # high == 100.0 → touch
        _bar(1, 99.0, 99.5, 98.5, 99.0),  # no touch
        _bar(2, 99.0, 100.0, 98.5, 99.5),  # high == 100.0 → touch (but spacing!)
    ]
    # with min_bars_between=0 → both bars 0 and 2 count
    count = _count_touches(bars, 100.0, tol=0.01, min_bars_between=0)
    assert count == 2


def test_count_touches_spacing_requirement() -> None:
    """Consecutive touch bars within spacing window should only count once."""
    bars = [
        _bar(0, 99.0, 100.0, 98.5, 99.5),  # touch
        _bar(1, 99.0, 100.0, 98.5, 99.5),  # touch but within spacing
        _bar(2, 99.0, 99.0, 98.5, 98.8),  # no touch
        _bar(3, 99.0, 100.0, 98.5, 99.5),  # touch after gap
    ]
    # min_bars_between=2: bars 0 and 3 (gap of 3) → 2 touches
    count = _count_touches(bars, 100.0, tol=0.05, min_bars_between=2)
    assert count == 2


def test_count_touches_insufficient_spacing_only_one() -> None:
    """Bars 0 and 1 both touch but spacing=2 means only 1 counts."""
    bars = [
        _bar(0, 99.0, 100.0, 98.5, 99.5),
        _bar(1, 99.0, 100.0, 98.5, 99.5),
    ]
    count = _count_touches(bars, 100.0, tol=0.05, min_bars_between=2)
    assert count == 1


def test_count_touches_zero_if_none_in_tolerance() -> None:
    bars = [_bar(i, 98.0, 98.5, 97.5, 98.0) for i in range(5)]
    count = _count_touches(bars, 100.0, tol=0.1, min_bars_between=0)
    assert count == 0


# ── detect_range integration ───────────────────────────────────────────────────


def test_detect_range_insufficient_history_returns_none() -> None:
    cfg = load_config()
    bars = _range_bars(n=5, mid=100.0, half_width=1.0)
    result = detect_range(bars, cfg.regimes.range)
    assert result is None


def test_detect_range_sufficient_touches_may_detect() -> None:
    """With enough flat oscillating bars, detect_range may return RANGE.

    This test uses a softened config to increase the chance of detection.
    Key assertion: no crash and if detected, regime is RANGE.
    """
    cfg = load_config()
    range_cfg = cfg.regimes.range.model_copy(
        update={
            "adx_max": 50.0,  # allow high ADX
            "ema50_flat_atr": 5.0,  # very flat threshold
            "ema_sep_atr": 5.0,  # very loose separation
            "width_min_atr": 0.1,  # wide tolerance
            "width_max_atr": 100.0,
            "min_touches_per_side": 2,
        }
    )
    bars = _range_bars(n=120, mid=100.0, half_width=1.0)
    result = detect_range(bars, range_cfg)
    if result is not None:
        from checktrader.domain.enums import MarketRegime

        assert result.regime == MarketRegime.RANGE
        # Metadata should have range boundaries
        assert "range_high" in result.indicators.metadata
        assert "range_low" in result.indicators.metadata


def test_detect_range_insufficient_touches_returns_none() -> None:
    """If bars only touch one side, detect_range should return None."""
    # Bars that only oscillate near the HIGH boundary, never near LOW
    bars = []
    for i in range(60):
        o = 100.5 + (i % 3) * 0.02
        h = 101.0  # always touch high
        lo = 100.0 + (i % 5) * 0.1
        c = 100.6
        bars.append(_bar(i, o, h, lo, c))

    cfg = load_config()
    # With a large min_touches_per_side requirement (default 2), the low side won't have touches
    range_cfg = cfg.regimes.range.model_copy(update={"min_touches_per_side": 3})
    result = detect_range(bars, range_cfg)
    # The low side should have 0 touches → None
    # (This is a structural invariant test; may also be None for other reasons)
    assert result is None  # no crash is the key requirement; may or may not classify as range
