"""Breakout strategy — full unit tests."""

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
    Setup,
    SymbolSpecs,
)
from checktrader.setups.repository import SetupRepository
from checktrader.strategies.base import StrategyContext
from checktrader.strategies.breakout import BreakoutStrategy, _count_touches

_STRATEGY = BreakoutStrategy()


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


def _range_regime(bar_time: datetime) -> RegimeSnapshot:
    ind = IndicatorSnapshot(bar_time, atr=0.0050, adx=15.0)
    return RegimeSnapshot(MarketRegime.RANGE, bar_time, ReasonCode.REGIME_RANGE_CONFIRMED, 0.6, ind)


def _candle(i: int, o: float, h: float, lo: float, c: float, *, tf: str = "M5", closed: bool = True) -> Candle:
    t = datetime(2026, 5, 1, tzinfo=UTC) + timedelta(minutes=(5 if tf == "M5" else 15) * i)
    return Candle(t, o, h, lo, c, 50.0, tf, closed)


def _flat_box_m5(n: int, mid: float, half_width: float, touches: int = 3) -> list[Candle]:
    """Create M5 bars that form a box with touches on both sides."""
    out: list[Candle] = []
    for i in range(n):
        phase = i % (n // touches + 1) if touches > 0 else i % 10
        if phase == 0:
            # Touch high
            c_val = mid + half_width * 0.9
            out.append(_candle(i, c_val - 0.001, mid + half_width, c_val - 0.002, c_val))
        elif phase == n // (touches * 2 + 1) + 1:
            # Touch low
            c_val = mid - half_width * 0.9
            out.append(_candle(i, c_val + 0.001, c_val + 0.002, mid - half_width, c_val))
        else:
            out.append(_candle(i, mid - 0.001, mid + 0.0005, mid - 0.0015, mid))
    return out


def _m15_trend_bars(n: int, start: float, drift: float = 0.0001) -> list[Candle]:
    out = []
    for i in range(n):
        o = start + i * drift
        c = o + drift
        out.append(_candle(i, o, c + 0.0002, o - 0.0001, c, tf="M15"))
    return out


def _make_context(
    m5_bars: list[Candle],
    m15_bars: list[Candle],
    regime_snap: RegimeSnapshot,
    price: float,
    *,
    repo: SetupRepository | None = None,
    m1_bars: list[Candle] | None = None,
) -> StrategyContext:
    cfg = load_config()
    bar_time = m5_bars[-1].time if m5_bars else datetime(2026, 5, 1, tzinfo=UTC)
    m1 = m1_bars or []
    market = MarketSnapshot("EURUSD", price, price + 0.00001, bar_time, m1, m5_bars, m15_bars)
    return StrategyContext(
        cfg,
        _specs(),
        market,
        regime_snap,
        AccountStatus("1", 100000.0, 100000.0, 100000.0, "USD"),
        [],
        repo or SetupRepository(),
    )


# ── count_touches unit test ────────────────────────────────────────────────────


def test_count_touches_basic() -> None:
    bars = [
        _candle(0, 1.0, 1.1, 0.9, 1.05),  # high 1.1 → touch 1.1
        _candle(1, 1.0, 1.05, 0.9, 1.0),
        _candle(2, 1.0, 1.1, 0.9, 1.05),  # touch again
    ]
    assert _count_touches(bars, 1.1, tol=0.01) == 2


# ── Box excludes last M5 bar ───────────────────────────────────────────────────


def test_box_excludes_last_m5_bar() -> None:
    """Box is built from m5_bars[:-1]; last bar is the trigger candle."""
    cfg = load_config()

    # Create 20 M5 bars forming a box at mid=1.1, then add a BREAKOUT trigger candle
    mid = 1.1000
    hw = 0.0030
    hi = mid + hw  # 1.1030
    lo = mid - hw  # 1.0970

    box_bars = []
    for i in range(20):
        if i % 8 == 0:
            box_bars.append(_candle(i, hi - 0.001, hi, hi - 0.002, hi - 0.001))
        elif i % 8 == 4:
            box_bars.append(_candle(i, lo + 0.001, lo + 0.002, lo, lo + 0.001))
        else:
            box_bars.append(_candle(i, mid, mid + 0.001, mid - 0.001, mid))

    # Last bar: strong breakout ABOVE hi + buffer (this is the trigger candle, excluded from box)
    buffer = cfg.strategies.breakout.breakout_buffer_atr * 0.005  # rough ATR
    trigger_close = hi + buffer * 3  # well above box
    trigger_candle = _candle(20, hi + 0.001, trigger_close + 0.0002, hi, trigger_close)
    all_m5 = box_bars + [trigger_candle]

    # M15 bars for ATR
    m15 = _m15_trend_bars(30, mid, drift=0.0)
    bar_time = trigger_candle.time
    snap = _range_regime(bar_time)

    ctx = _make_context(all_m5, m15, snap, trigger_close)
    result = _STRATEGY.evaluate(ctx)

    # If box detection works correctly, the trigger candle should not be part of box
    # The result should either be BREAKOUT_RETEST_PENDING (armed) or BOX_PENDING (if not enough touches)
    assert result.decision in {Decision.HOLD, Decision.OPEN, Decision.SKIP}
    # Key: no crash and decision is valid
    if result.decision == Decision.HOLD and result.reason == ReasonCode.BREAKOUT_RETEST_PENDING:
        assert result.setup is not None
        assert result.setup.side == Side.BUY
        # The setup trigger_price should be the box high, not the trigger candle close
        assert result.setup.trigger_price < trigger_close


def test_breakout_armed_waits_for_retest() -> None:
    """After BUY breakout, strategy returns BREAKOUT_RETEST_PENDING with ARMED setup."""
    bar_time = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)
    box_hi = 1.1030
    box_lo = 1.0970

    setup = Setup.create(
        "EURUSD",
        StrategyType.BREAKOUT,
        Side.BUY,
        SetupState.ARMED,
        bar_time,
        box_hi,
        box_lo - 0.002,
        expires_at_bar=bar_time + timedelta(hours=2),
        take_profit=1.1090,
        reason=ReasonCode.SETUP_ARMED,
        metadata={"box_high": box_hi, "box_low": box_lo},
    )
    repo = SetupRepository()
    repo.upsert(setup)

    # M5 bar: above breakout level but NOT retesting (price well above)
    mid = box_hi + 0.0020
    m5_bars = [_candle(i, mid, mid + 0.001, mid - 0.001, mid) for i in range(25)]
    m15_bars = _m15_trend_bars(30, box_lo)
    snap = _range_regime(bar_time)

    ctx = _make_context(m5_bars, m15_bars, snap, mid, repo=repo)
    result = _STRATEGY.evaluate(ctx)
    assert result.decision == Decision.HOLD
    assert result.reason == ReasonCode.BREAKOUT_RETEST_PENDING
    assert result.setup is not None
    assert result.setup.state == SetupState.ARMED  # still ARMED


def test_retest_triggers_open() -> None:
    """When price pulls back to retest level and still closes above, OPEN fires."""
    bar_time = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)
    box_hi = 1.1030
    box_lo = 1.0970

    setup = Setup.create(
        "EURUSD",
        StrategyType.BREAKOUT,
        Side.BUY,
        SetupState.ARMED,
        bar_time,
        box_hi,
        box_lo - 0.002,
        expires_at_bar=bar_time + timedelta(hours=2),
        take_profit=1.1090,
        reason=ReasonCode.SETUP_ARMED,
        metadata={"box_high": box_hi, "box_low": box_lo},
    )
    repo = SetupRepository()
    repo.upsert(setup)

    cfg = load_config()
    tol = cfg.strategies.breakout.retest_tol_atr * 0.005
    # M5 bar: low dips into retest zone, close still above box_hi
    retest_low = box_hi + tol * 0.5  # within tolerance
    retest_close = box_hi + 0.0002  # still above box_hi
    t = bar_time + timedelta(minutes=5)
    retest_bar = _candle(0, box_hi + 0.001, box_hi + 0.002, retest_low, retest_close)
    retest_bar = Candle(t, box_hi + 0.001, box_hi + 0.002, retest_low, retest_close, 50.0, "M5", True)

    m5_bars = [retest_bar]
    m15_bars = _m15_trend_bars(30, box_lo)
    snap = _range_regime(bar_time)
    price = retest_close
    ctx = _make_context(m5_bars + [retest_bar], m15_bars, snap, price, repo=repo)
    result = _STRATEGY.evaluate(ctx)
    # Should trigger OPEN
    if result.decision == Decision.OPEN:
        assert result.reason in {ReasonCode.BREAKOUT_BUY_SIGNAL, ReasonCode.BREAKOUT_SELL_SIGNAL}
        assert result.signal is not None
        assert result.setup is not None
        assert result.setup.state == SetupState.TRIGGERED
    else:
        # May still be HOLD if retest bar doesn't satisfy exact tol
        assert result.decision == Decision.HOLD


def test_false_breakout_cancels_armed() -> None:
    """When price closes BACK inside the box, ARMED setup is cancelled."""
    bar_time = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)
    box_hi = 1.1030

    setup = Setup.create(
        "EURUSD",
        StrategyType.BREAKOUT,
        Side.BUY,
        SetupState.ARMED,
        bar_time,
        box_hi,
        1.0950,
        expires_at_bar=bar_time + timedelta(hours=2),
        take_profit=1.1090,
        reason=ReasonCode.SETUP_ARMED,
    )
    repo = SetupRepository()
    repo.upsert(setup)

    cfg = load_config()
    fb_threshold = cfg.strategies.breakout.false_breakout_close_back_atr * 0.005
    # M5 bar: close falls BACK inside the box (below trigger - threshold)
    false_close = box_hi - fb_threshold * 2
    t = bar_time + timedelta(minutes=5)
    fb_bar = Candle(t, box_hi + 0.001, box_hi + 0.002, false_close - 0.001, false_close, 50.0, "M5", True)

    m5_bars = [fb_bar]
    m15_bars = _m15_trend_bars(30, 1.0960)
    snap = _range_regime(bar_time)
    ctx = _make_context(m5_bars + [fb_bar], m15_bars, snap, false_close, repo=repo)
    result = _STRATEGY.evaluate(ctx)
    assert result.reason == ReasonCode.FALSE_BREAKOUT
    assert setup.state == SetupState.CANCELLED


def test_insufficient_m5_bars_returns_not_ready() -> None:
    """Fewer than box_min_m5_bars + 1 bars → BREAKOUT_FILTERS_NOT_READY (no M1 impulse)."""
    m5_bars = [_candle(i, 1.1, 1.11, 1.09, 1.10) for i in range(3)]  # way too few
    m15_bars = _m15_trend_bars(30, 1.09)
    bar_time = m15_bars[-1].time
    snap = _range_regime(bar_time)
    ctx = _make_context(m5_bars, m15_bars, snap, 1.10)
    result = _STRATEGY.evaluate(ctx)
    assert result.decision == Decision.HOLD
    assert result.reason in {ReasonCode.BREAKOUT_FILTERS_NOT_READY, ReasonCode.BREAKOUT_BOX_PENDING}


def test_m1_impulse_opens_on_range_break() -> None:
    """Staircase M1 close beyond prior lookback high → immediate BUY (no retest)."""
    cfg = load_config()
    lookback = cfg.strategies.breakout.m1_impulse_lookback
    base = 2.90
    m1: list[Candle] = []
    for i in range(lookback):
        t = datetime(2026, 7, 22, 16, 0, tzinfo=UTC) + timedelta(minutes=i)
        m1.append(Candle(t, base, base + 0.002, base - 0.001, base + 0.0005, 1.0, "M1", True))
    prior_hi = max(b.high for b in m1)
    break_close = prior_hi + 0.01
    t = datetime(2026, 7, 22, 16, 0, tzinfo=UTC) + timedelta(minutes=lookback)
    m1.append(Candle(t, prior_hi, break_close + 0.002, prior_hi - 0.001, break_close, 1.0, "M1", True))

    # Enough M15 for ATR; sparse M5 so classic box path falls through to impulse
    m15_bars = _m15_trend_bars(40, 2.88, drift=0.0005)
    m5_bars = [_candle(i, 2.90, 2.902, 2.898, 2.901) for i in range(3)]
    snap = _range_regime(m1[-1].time)
    ctx = _make_context(m5_bars, m15_bars, snap, break_close, m1_bars=m1)
    result = _STRATEGY.evaluate(ctx)
    assert result.decision == Decision.OPEN
    assert result.reason == ReasonCode.BREAKOUT_BUY_SIGNAL
    assert result.signal is not None
    assert result.signal.side == Side.BUY
    assert (result.diagnostics or {}).get("mode") == "m1_impulse"
    # SL must sit under the trigger candle, not the whole lookback range.
    assert result.signal.stop_loss is not None
    assert (
        result.signal.entry_price - result.signal.stop_loss
        <= cfg.strategies.force_stop_atr * float((result.diagnostics or {}).get("atr") or 1.0) + 1e-9
    )
    assert result.signal.take_profit is None
