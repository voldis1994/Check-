"""ATR-adaptive SL + no instant regime-flip kills."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from checktrader.config.loader import load_config
from checktrader.config.models import ManagementConfig
from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, Side, StrategyType
from checktrader.domain.models import Candle, Position, SymbolSpecs
from checktrader.management.atr_stops import atr_for_stops, robust_atr, stop_target_distance, trail_lock_distance
from checktrader.management.exits import regime_flip_action
from checktrader.management.trailing import trailing_action
from checktrader.strategies.exits import hard_take_profit_price


def _ng_specs() -> SymbolSpecs:
    return SymbolSpecs("NATURALGAS", 3, 0.001, 0.001, 0.001, 0.01, 100.0, 0.01, 100.0, 0.0, 0.0)


def _bar(i: int, *, tr: float = 0.04) -> Candle:
    t = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i)
    o = 3.0
    return Candle(t, o, o + tr, o - 0.001, o + tr * 0.2, 1.0, True)


def test_hard_take_profit_disabled_returns_none() -> None:
    assert hard_take_profit_price(entry=2.90, stop=2.88, side=Side.BUY, rr=1.5, enabled=False) is None


def test_default_config_no_instant_regime_flip() -> None:
    cfg = load_config()
    assert cfg.management.exit_on_regime_flip is False
    assert cfg.management.regime_flip_min_hold_seconds == 180.0
    assert cfg.strategies.force_stop_atr == 1.0


def test_regime_flip_disabled_keeps_fresh_trade() -> None:
    cfg = ManagementConfig(exit_on_regime_flip=False)
    pos = Position(
        "p1",
        "NATURALGAS",
        Side.BUY,
        0.02,
        3.0,
        2.9,
        None,
        datetime.now(UTC),
        StrategyType.BREAKOUT,
    )
    action = regime_flip_action(pos, MarketRegime.TREND_DOWN, cfg)
    assert action.decision is Decision.HOLD


def test_regime_flip_respects_min_hold() -> None:
    cfg = ManagementConfig(exit_on_regime_flip=True, regime_flip_min_hold_seconds=180.0)
    now = datetime.now(UTC)
    pos = Position(
        "p1",
        "NATURALGAS",
        Side.BUY,
        0.02,
        3.0,
        2.9,
        None,
        now - timedelta(seconds=10),
        StrategyType.BREAKOUT,
    )
    assert regime_flip_action(pos, MarketRegime.TREND_DOWN, cfg, now=now).decision is Decision.HOLD
    pos.opened_at = now - timedelta(seconds=200)
    assert regime_flip_action(pos, MarketRegime.TREND_DOWN, cfg, now=now).decision is Decision.CLOSE
    assert regime_flip_action(pos, MarketRegime.TREND_DOWN, cfg, now=now).reason is ReasonCode.EXIT_REGIME_FLIP


def test_robust_atr_caps_spike() -> None:
    # Quiet bars then one huge spike TR
    bars = [_bar(i, tr=0.04) for i in range(40)]
    bars.append(_bar(40, tr=0.40))  # 10x spike
    value = robust_atr(bars, 14)
    assert value is not None
    # Must not return the full spiked ATR (~would drive ~300pt stops)
    assert value < 0.12


def test_atr_for_stops_prefers_m15() -> None:
    m15 = [_bar(i, tr=0.04) for i in range(40)]
    m1 = [_bar(i, tr=0.20) for i in range(40)]
    a = atr_for_stops(m15=m15, m1=m1, period=14)
    assert a is not None
    assert a < 0.10


def test_stop_distance_is_one_atr_mult() -> None:
    cfg = load_config()
    atr = 0.04
    dist = stop_target_distance(_ng_specs(), cfg.strategies, atr)
    assert abs(dist - atr * 1.0) < 1e-12


def test_trailing_still_works() -> None:
    cfg = ManagementConfig()
    specs = _ng_specs()
    atr = 0.04
    lock = trail_lock_distance(specs, cfg, atr)
    entry = 2.90
    pos = Position(
        "p1",
        "NATURALGAS",
        Side.BUY,
        0.02,
        entry,
        entry - atr,
        None,
        datetime.now(UTC),
        StrategyType.BREAKOUT,
    )
    action = trailing_action(pos, entry + lock * 1.05, atr, MarketRegime.TREND_UP, cfg, specs)
    assert action.decision is Decision.MODIFY
