"""Trailing exit — ATR lock-back (~20 NATURALGAS points), no hard TP."""

from __future__ import annotations

from datetime import UTC, datetime

from checktrader.config.loader import load_config
from checktrader.config.models import ManagementConfig
from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, Side, StrategyType
from checktrader.domain.models import Position
from checktrader.management.trailing import trail_lock_distance, trailing_action
from checktrader.strategies.exits import hard_take_profit_price


def test_hard_take_profit_disabled_returns_none() -> None:
    assert hard_take_profit_price(entry=2.90, stop=2.88, side=Side.BUY, rr=1.5, enabled=False) is None


def test_default_config_atr_lock() -> None:
    cfg = load_config()
    assert cfg.management.hard_take_profit is False
    assert cfg.management.trailing_lock_atr == 0.50
    # 20 NATURALGAS points (point=0.001) ≈ 0.02; at ATR=0.04 → 0.50 ATR
    assert abs(trail_lock_distance(0.04, cfg.management) - 0.02) < 1e-9


def test_trailing_ratchets_past_breakeven() -> None:
    """After BE at entry, further profit must pull SL forward (not freeze)."""
    cfg = ManagementConfig()
    atr = 0.04
    lock = trail_lock_distance(atr, cfg)  # 0.02 ≈ 20pts
    entry = 2.90
    # Already at breakeven
    pos = Position(
        "p1",
        "NATURALGAS",
        Side.BUY,
        0.02,
        entry,
        entry + 0.002,
        None,
        datetime.now(UTC),
        StrategyType.BREAKOUT,
    )
    # Price moved ~1.5 locks ahead → SL should sit ~0.5 lock above entry
    price = entry + lock * 1.5
    action = trailing_action(pos, price, atr_value=atr, regime=MarketRegime.TREND_UP, config=cfg)
    assert action.decision is Decision.MODIFY
    assert action.reason is ReasonCode.TRAILING_MOVE
    assert action.stop_loss is not None
    assert action.stop_loss > entry + 0.002
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
        entry + lock * 0.5,
        None,
        datetime.now(UTC),
        StrategyType.BREAKOUT,
    )
    price = entry + lock * 2.0
    action = trailing_action(pos, price, atr_value=atr, regime=MarketRegime.TRANSITION, config=cfg)
    assert action.decision is Decision.MODIFY
    assert action.stop_loss == price - lock
