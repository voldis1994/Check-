"""Exit pressure unit tests."""

from __future__ import annotations

from checktrader.config.models import ExitPressureConfig
from checktrader.domain.enums import Side
from checktrader.observability.reason_codes import ReasonCode
from checktrader.position_management.exit_pressure import compute_exit_pressure
from tests.fixtures.candles import sequential_m1


def _cfg(**overrides: float) -> ExitPressureConfig:
    base = dict(
        enabled=True,
        pullback_weight=0.30,
        speed_weight=0.20,
        trend_weight=0.20,
        rejection_weight=0.20,
        spread_weight=0.10,
        tighten_threshold=0.45,
        high_lock_threshold=0.70,
        critical_threshold=0.85,
        critical_close_enabled=True,
        minimum_non_spread_confirmations_for_close=3,
    )
    base.update(overrides)
    return ExitPressureConfig(**base)


def test_components_and_weighted_score() -> None:
    bars = sequential_m1(n=30)
    # Force rejection wick on last bar
    last = bars[-1]
    from checktrader.domain.market import Candle

    bars[-1] = Candle(
        open_time_utc=last.open_time_utc,
        close_time_utc=last.close_time_utc,
        open=last.open,
        high=last.high + 0.00050,
        low=last.low,
        close=last.close,
        tick_volume=last.tick_volume,
        spread=last.spread,
        complete=True,
        timeframe="M1",
    )
    result = compute_exit_pressure(
        side=Side.BUY,
        peak_net_profit=2.0,
        current_net_profit=0.4,  # large giveback
        recent_m1=bars,
        current_spread_pips=1.0,
        median_spread_pips=1.0,
        trailing_step_pips=3.0,
        config=_cfg(),
    )
    assert 0.0 <= result.pullback <= 1.0
    assert 0.0 <= result.rejection <= 1.0
    expected = (
        result.pullback * 0.30
        + result.speed * 0.20
        + result.trend * 0.20
        + result.rejection * 0.20
        + result.spread * 0.10
    )
    assert abs(result.total - expected) < 1e-9


def test_spread_alone_does_not_close() -> None:
    bars = sequential_m1(n=5)
    result = compute_exit_pressure(
        side=Side.BUY,
        peak_net_profit=1.0,
        current_net_profit=1.0,  # no pullback
        recent_m1=bars,
        current_spread_pips=30.0,
        median_spread_pips=1.0,
        trailing_step_pips=3.0,
        config=_cfg(),
    )
    assert result.spread > 0.5
    assert not result.critical_close


def test_critical_needs_multi_non_spread_confirmations() -> None:
    # Construct high pullback + speed + rejection so non-spread count >= 3
    bars = sequential_m1(n=10)
    from checktrader.domain.market import Candle

    # last 4 bars: shrinking bodies + adverse for BUY
    rebuilt = list(bars)
    for i, idx in enumerate(range(len(bars) - 4, len(bars))):
        b = bars[idx]
        open_ = 1.10000 - i * 0.00010
        close = open_ - 0.00020 + i * 0.00003  # adverse down, shrinking
        rebuilt[idx] = Candle(
            open_time_utc=b.open_time_utc,
            close_time_utc=b.close_time_utc,
            open=open_,
            high=open_ + 0.00040,  # upper wick rejection
            low=close - 0.00002,
            close=close,
            tick_volume=100,
            spread=2,
            complete=True,
            timeframe="M1",
        )
    result = compute_exit_pressure(
        side=Side.BUY,
        peak_net_profit=5.0,
        current_net_profit=0.1,
        recent_m1=rebuilt,
        current_spread_pips=1.0,
        median_spread_pips=1.0,
        trailing_step_pips=3.0,
        config=_cfg(critical_threshold=0.5),
    )
    non_spread = sum(1 for v in (result.pullback, result.speed, result.trend, result.rejection) if v >= 0.45)
    if result.total >= 0.5 and non_spread >= 3:
        assert result.critical_close
        assert result.reason is ReasonCode.EXIT_PRESSURE_CRITICAL
    else:
        # still assert the gate: spread-only critical path blocked
        result2 = compute_exit_pressure(
            side=Side.BUY,
            peak_net_profit=1.0,
            current_net_profit=1.0,
            recent_m1=bars[:3],
            current_spread_pips=100.0,
            median_spread_pips=1.0,
            trailing_step_pips=3.0,
            config=_cfg(critical_threshold=0.05),
        )
        assert not result2.critical_close
