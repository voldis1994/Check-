"""ATR SL / trailing — ~100 NATURALGAS points or ~10 FX pips via ATR."""

from __future__ import annotations

from datetime import UTC, datetime

from checktrader.config.loader import load_config
from checktrader.config.models import ManagementConfig
from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, Side, StrategyType
from checktrader.domain.models import Position
from checktrader.management.atr_stops import atr_distance, clamp_stop_price, distance_points
from checktrader.management.breakeven import breakeven_action
from checktrader.management.trailing import trail_lock_distance, trail_start_distance, trailing_action
from checktrader.strategies.exits import hard_take_profit_price


def test_hard_take_profit_disabled_returns_none() -> None:
    assert hard_take_profit_price(entry=2.90, stop=2.88, side=Side.BUY, rr=1.5, enabled=False) is None


def test_default_config_atr_stop_and_trail() -> None:
    cfg = load_config()
    assert cfg.management.hard_take_profit is False
    assert cfg.strategies.force_stop_atr == 2.5
    assert cfg.management.trailing_lock_atr == 1.0
    assert cfg.management.trailing_start_atr == 0.75
    # NATURALGAS ref: ATR=0.04 point=0.001 → SL≈100pts, trail lock≈40pts
    atr = 0.04
    point = 0.001
    assert abs(distance_points(atr_distance(atr, 2.5), point) - 100.0) < 1e-9
    assert abs(distance_points(trail_lock_distance(atr, cfg.management), point) - 40.0) < 1e-9


def test_eurusd_style_ten_pips_via_atr() -> None:
    # EURUSD 5-digit: 10 pips = 0.001 = 100 points when point=0.00001
    atr = 0.0008
    point = 0.00001
    # ~1.25 ATR ≈ 10 pips at this ATR
    assert abs(distance_points(atr_distance(atr, 1.25), point) - 100.0) < 1e-6


def test_clamp_stop_enforces_min_and_max_atr() -> None:
    entry = 3.0
    atr = 0.04
    # Too tight → expand to min 1.0 ATR
    tight = clamp_stop_price(entry=entry, stop=2.995, side=Side.BUY, atr_value=atr, min_atr=1.0, max_atr=2.5)
    assert abs((entry - tight) - 0.04) < 1e-9
    # Too wide → pull to max 2.5 ATR
    wide = clamp_stop_price(entry=entry, stop=2.0, side=Side.BUY, atr_value=atr, min_atr=1.0, max_atr=2.5)
    assert abs((entry - wide) - 0.10) < 1e-9


def test_trailing_starts_on_atr_profit_not_tiny_r() -> None:
    cfg = ManagementConfig()
    atr = 0.04
    lock = trail_lock_distance(atr, cfg)
    start = trail_start_distance(atr, cfg)
    entry = 2.90
    # Wide initial SL (~100pts) — RR gate would starve; ATR start must fire.
    pos = Position(
        "p1",
        "NATURALGAS",
        Side.BUY,
        0.02,
        entry,
        entry - atr * 2.5,
        None,
        datetime.now(UTC),
        StrategyType.BREAKOUT,
    )
    # Below start → hold
    action = trailing_action(
        pos, entry + start * 0.5, atr_value=atr, regime=MarketRegime.TREND_UP, config=cfg
    )
    assert action.decision is Decision.HOLD
    # At need=max(start,lock)=lock when lock>start... need = max(0.75,1.0)*atr = lock
    price = entry + max(start, lock)
    action = trailing_action(pos, price, atr_value=atr, regime=MarketRegime.TREND_UP, config=cfg)
    assert action.decision is Decision.MODIFY
    assert action.reason is ReasonCode.TRAILING_MOVE
    assert action.stop_loss is not None
    assert abs(action.stop_loss - (price - lock)) < 1e-9


def test_trailing_keeps_ratcheting() -> None:
    cfg = ManagementConfig()
    atr = 0.04
    lock = trail_lock_distance(atr, cfg)
    entry = 2.90
    pos = Position(
        "p1",
        "NATURALGAS",
        Side.BUY,
        0.02,
        entry,
        entry + lock * 0.2,
        None,
        datetime.now(UTC),
        StrategyType.BREAKOUT,
    )
    price = entry + lock * 2.0
    action = trailing_action(pos, price, atr_value=atr, regime=MarketRegime.TRANSITION, config=cfg)
    assert action.decision is Decision.MODIFY
    assert action.stop_loss == price - lock


def test_breakeven_uses_atr_trigger() -> None:
    from checktrader.domain.models import SymbolSpecs

    cfg = ManagementConfig()
    atr = 0.04
    entry = 2.90
    specs = SymbolSpecs("NATURALGAS", 3, 0.001, 0.001, 0.01, 0.01, 100.0, 0.01, 100.0, 0.0, 0.0)
    pos = Position(
        "p1",
        "NATURALGAS",
        Side.BUY,
        0.02,
        entry,
        entry - atr * 2.5,
        None,
        datetime.now(UTC),
        StrategyType.BREAKOUT,
    )
    # 0.5 ATR profit — below BE trigger 1.0
    action = breakeven_action(pos, entry + atr * 0.5, cfg, specs, atr_value=atr)
    assert action.decision is Decision.HOLD
    # 1.0 ATR profit — move to BE+
    action = breakeven_action(pos, entry + atr * 1.0, cfg, specs, atr_value=atr)
    assert action.decision is Decision.MODIFY
    assert action.reason is ReasonCode.BREAKEVEN_MOVE
    assert action.stop_loss is not None
    assert action.stop_loss > entry
