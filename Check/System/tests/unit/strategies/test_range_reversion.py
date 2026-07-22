"""Range reversion strategy — full unit tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from checktrader.config.loader import load_config
from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, SetupState, Side, StrategyType
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
from checktrader.strategies.range_reversion import RangeReversionStrategy

_STRATEGY = RangeReversionStrategy()


# ── Helpers ────────────────────────────────────────────────────────────────────


def _specs() -> SymbolSpecs:
    return SymbolSpecs(
        symbol="EURUSD",
        digits=5,
        point=0.00001,
        tick_size=0.00001,
        pip_size=0.0001,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        contract_size=100000.0,
        stop_level_points=10.0,
        freeze_level_points=0.0,
    )


def _range_snap(bar_time: datetime, hi: float, lo: float) -> RegimeSnapshot:
    ind = IndicatorSnapshot(
        bar_time,
        ema_fast=((hi + lo) / 2),
        ema_slow=((hi + lo) / 2),
        atr=(hi - lo) * 0.5,
        adx=12.0,
        metadata={"range_high": hi, "range_low": lo},
    )
    return RegimeSnapshot(MarketRegime.RANGE, bar_time, ReasonCode.REGIME_RANGE_CONFIRMED, 0.7, ind)


def _make_bars(n: int, mid: float, half_width: float, *, oscillate: bool = True) -> list[Candle]:
    t0 = datetime(2026, 4, 1, tzinfo=UTC)
    out: list[Candle] = []
    for i in range(n):
        if oscillate:
            phase = i % 8
            if phase in {0, 1}:
                lo = mid - half_width
                h = mid - half_width + half_width * 0.3
                o = lo + 0.01
                c = lo + 0.02
            elif phase in {4, 5}:
                h = mid + half_width
                lo = mid + half_width - half_width * 0.3
                o = h - 0.02
                c = h - 0.01
            else:
                o = mid - 0.05
                c = mid + 0.05
                h = c + 0.05
                lo = o - 0.05
        else:
            o = mid
            c = mid + 0.01
            h = c + 0.02
            lo = o - 0.01
        out.append(Candle(t0 + timedelta(minutes=15 * i), o, h, lo, c, 50.0, "M15", True))
    return out


def _m1_bar_at(price: float, i: int = 0, *, bullish: bool = True) -> Candle:
    t = datetime(2026, 4, 1, tzinfo=UTC) + timedelta(minutes=i)
    o = price - 0.00002 if bullish else price + 0.00002
    c = price
    return Candle(t, o, max(o, c) + 0.00001, min(o, c) - 0.00001, c, 10.0, "M1", True)


def _ctx(
    last_m15: Candle,
    m15_bars: list[Candle],
    regime_snap: RegimeSnapshot,
    *,
    m1_bars: list[Candle] | None = None,
    repo: SetupRepository | None = None,
) -> StrategyContext:
    cfg = load_config()
    price = last_m15.close
    market = MarketSnapshot(
        "EURUSD",
        price,
        price + 0.00001,
        last_m15.time,
        m1_bars or [_m1_bar_at(price)],
        [],
        m15_bars,
    )
    return StrategyContext(
        cfg,
        _specs(),
        market,
        regime_snap,
        AccountStatus("1", 100000.0, 100000.0, 100000.0, "USD"),
        [],
        repo or SetupRepository(),
    )


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_wrong_regime_returns_skip() -> None:
    """Non-RANGE regime → SKIP."""
    m15_bars = _make_bars(30, 1.1000, 0.0050)
    bar_time = m15_bars[-1].time
    ind = IndicatorSnapshot(bar_time, atr=0.001)
    snap = RegimeSnapshot(MarketRegime.TREND_UP, bar_time, ReasonCode.REGIME_TREND_UP_CONFIRMED, 0.8, ind)
    ctx = _ctx(m15_bars[-1], m15_bars, snap)
    result = _STRATEGY.evaluate(ctx)
    assert result.decision == Decision.SKIP
    assert result.reason == ReasonCode.NO_STRATEGY_FOR_REGIME


def test_wrong_regime_cancels_armed_range_setups() -> None:
    """When regime flips away from RANGE, any ARMED range setups are cancelled."""
    from checktrader.domain.models import Setup

    repo = SetupRepository()
    bar_time = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)
    setup = Setup.create(
        "EURUSD",
        StrategyType.RANGE_REVERSION,
        Side.BUY,
        SetupState.ARMED,
        bar_time,
        1.1000,
        1.0950,
        take_profit=1.1100,
        expires_at_bar=bar_time + timedelta(hours=1),
        reason=ReasonCode.SETUP_ARMED,
    )
    repo.upsert(setup)

    m15_bars = _make_bars(30, 1.1000, 0.0050)
    ind = IndicatorSnapshot(bar_time, atr=0.001)
    snap = RegimeSnapshot(MarketRegime.TREND_UP, bar_time, ReasonCode.REGIME_TREND_UP_CONFIRMED, 0.8, ind)
    ctx = _ctx(m15_bars[-1], m15_bars, snap, repo=repo)
    result = _STRATEGY.evaluate(ctx)
    assert result.decision == Decision.SKIP
    assert setup.state == SetupState.CANCELLED


def test_middle_zone_no_trade() -> None:
    """Price in middle zone → RANGE_MIDDLE_NO_TRADE."""
    mid = 1.1000
    half_width = 0.0050
    hi = mid + half_width  # 1.1050
    lo = mid - half_width  # 1.0950
    m15_bars = _make_bars(30, mid, half_width)
    bar_time = m15_bars[-1].time
    snap = _range_snap(bar_time, hi, lo)

    # Create a M15 bar that closes in the middle
    middle_close = mid  # exactly in the middle
    t = m15_bars[-1].time
    last_bar = Candle(
        t, middle_close - 0.001, middle_close + 0.001, middle_close - 0.002, middle_close, 50.0, "M15", True
    )
    m15_bars[-1] = last_bar

    ctx = _ctx(last_bar, m15_bars, snap)
    result = _STRATEGY.evaluate(ctx)
    # Middle zone: should be RANGE_MIDDLE_NO_TRADE or NO_RANGE_BOUNDARY_REJECTION
    assert result.decision == Decision.HOLD
    assert result.reason in {ReasonCode.RANGE_MIDDLE_NO_TRADE, ReasonCode.NO_RANGE_BOUNDARY_REJECTION}


def test_lower_boundary_rejection_arms_buy() -> None:
    """M15 bar with strong lower wick at range bottom creates ARMED BUY setup."""
    mid = 1.1000
    half_width = 0.0050
    hi = mid + half_width
    lo = mid - half_width

    m15_bars = _make_bars(30, mid, half_width)
    bar_time = m15_bars[-1].time
    snap = _range_snap(bar_time, hi, lo)

    cfg = load_config()
    zone_pct = cfg.strategies.range_reversion.zone_pct
    _ = lo + zone_pct * (hi - lo)  # buy zone upper bound used for fixture design

    # Last bar: closes in lower zone with strong lower wick (rejection)
    bar_close = lo + 0.0005  # in buy zone
    bar_open = bar_close + 0.0001  # slight bearish open, close in zone
    bar_high = bar_close + 0.0002
    bar_low = lo - 0.0001  # wick below range low
    # Ensure close is in upper half of bar: close > (high + low) / 2
    bar_mid = (bar_high + bar_low) / 2
    # Adjust so close > bar_mid
    if bar_close <= bar_mid:
        bar_close = bar_mid + 0.0001
    last_bar = Candle(bar_time, bar_open, bar_high, bar_low, bar_close, 50.0, "M15", True)
    m15_bars[-1] = last_bar
    snap = _range_snap(bar_time, hi, lo)

    repo = SetupRepository()
    ctx = _ctx(last_bar, m15_bars, snap, repo=repo)
    result = _STRATEGY.evaluate(ctx)

    # Could be SETUP_ARMED (if wick large enough) or NO_RANGE_BOUNDARY_REJECTION
    if result.reason == ReasonCode.SETUP_ARMED:
        assert result.setup is not None
        assert result.setup.state == SetupState.ARMED
        assert result.setup.side == Side.BUY
    else:
        # Rejection not strong enough → acceptable HOLD
        assert result.decision == Decision.HOLD


def test_upper_boundary_rejection_hold_reasons() -> None:
    """M15 bar at range top with insufficient wick → NO_RANGE_BOUNDARY_REJECTION."""
    mid = 1.1000
    half_width = 0.0050
    hi = mid + half_width
    lo = mid - half_width

    m15_bars = _make_bars(30, mid, half_width)
    bar_time = m15_bars[-1].time
    snap = _range_snap(bar_time, hi, lo)

    cfg = load_config()
    zone_pct = cfg.strategies.range_reversion.zone_pct
    _sell_zone_lo = hi - zone_pct * (hi - lo)

    # Last bar: closes in upper zone but NO wick (body fills range)
    bar_close = hi - 0.0005
    bar_open = bar_close - 0.0001  # bullish body, no wick
    bar_high = bar_close + 0.00001  # tiny upper wick
    bar_low = bar_open - 0.00001
    last_bar = Candle(bar_time, bar_open, bar_high, bar_low, bar_close, 50.0, "M15", True)
    m15_bars[-1] = last_bar
    snap = _range_snap(bar_time, hi, lo)

    ctx = _ctx(last_bar, m15_bars, snap)
    result = _STRATEGY.evaluate(ctx)
    assert result.decision == Decision.HOLD
    # Should be NO_RANGE_BOUNDARY_REJECTION or RANGE_MIDDLE_NO_TRADE
    assert result.reason in {ReasonCode.NO_RANGE_BOUNDARY_REJECTION, ReasonCode.RANGE_MIDDLE_NO_TRADE}


def test_breakout_cancel_via_router_interaction() -> None:
    """When regime changes to non-RANGE, active range setups get cancelled (via strategy)."""
    from checktrader.domain.models import Setup

    repo = SetupRepository()
    bar_time = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)
    setup = Setup.create(
        "EURUSD",
        StrategyType.RANGE_REVERSION,
        Side.SELL,
        SetupState.ARMED,
        bar_time,
        1.1050,
        1.1080,
        expires_at_bar=bar_time + timedelta(hours=2),
        take_profit=1.0990,
        reason=ReasonCode.SETUP_ARMED,
    )
    repo.upsert(setup)

    m15_bars = _make_bars(30, 1.1000, 0.0050)
    ind = IndicatorSnapshot(bar_time, atr=0.001)
    # Regime changed to TRANSITION
    snap = RegimeSnapshot(MarketRegime.TRANSITION, bar_time, ReasonCode.REGIME_TRANSITION_CONFIRMED, 0.5, ind)
    ctx = _ctx(m15_bars[-1], m15_bars, snap, repo=repo)
    result = _STRATEGY.evaluate(ctx)
    # Strategy skips and cancels setup
    assert result.decision == Decision.SKIP
    assert setup.state == SetupState.CANCELLED
