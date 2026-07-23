"""Symbol-aware entry: open positions on another symbol must not freeze the chart."""

from __future__ import annotations

from datetime import UTC, datetime

from checktrader.config.loader import load_config
from checktrader.domain.enums import Decision, ReasonCode, Side, StrategyType
from checktrader.domain.models import LimitState, Position, StrategySignal, SymbolSpecs
from checktrader.risk.validator import validate_order


def test_other_symbol_position_does_not_block_entry() -> None:
    cfg = load_config()
    specs = SymbolSpecs("USDCHF", 5, 0.00001, 0.00001, 0.0001, 0.01, 100.0, 0.01, 100000.0, 0.0, 0.0)
    signal = StrategySignal(
        StrategyType.BREAKOUT,
        Side.BUY,
        "USDCHF",
        0.8800,
        0.8790,
        None,
        ReasonCode.FORCE_MOMENTUM_BUY,
    )
    # Flat on USDCHF; leftover NATURALGAS position must not block.
    positions = [
        Position(
            "broker-1",
            "NATURALGAS",
            Side.BUY,
            0.02,
            2.90,
            2.88,
            None,
            datetime.now(UTC),
            StrategyType.BREAKOUT,
        )
    ]
    result = validate_order(
        signal,
        config=cfg,
        specs=specs,
        account=None,
        positions=positions,
        limit_state=LimitState(trade_date=""),
        bid=0.8799,
        ask=0.8801,
        atr_value=0.001,
        now=datetime.now(UTC),
    )
    assert result.decision is Decision.ALLOW
    assert ReasonCode.RISK_POSITION_EXISTS not in result.messages


def test_same_symbol_position_still_blocks() -> None:
    cfg = load_config()
    specs = SymbolSpecs("NATURALGAS", 3, 0.001, 0.001, 0.01, 0.01, 100.0, 0.01, 100.0, 0.0, 0.0)
    signal = StrategySignal(
        StrategyType.BREAKOUT,
        Side.BUY,
        "NATURALGAS",
        2.90,
        2.897,
        None,
        ReasonCode.FORCE_MOMENTUM_BUY,
    )
    positions = [
        Position(
            "broker-1",
            "NATURALGAS",
            Side.BUY,
            0.02,
            2.88,
            2.86,
            None,
            datetime.now(UTC),
            StrategyType.BREAKOUT,
        )
    ]
    result = validate_order(
        signal,
        config=cfg,
        specs=specs,
        account=None,
        positions=positions,
        limit_state=LimitState(trade_date=""),
        bid=2.899,
        ask=2.901,
        atr_value=0.02,
        now=datetime.now(UTC),
    )
    assert result.decision is Decision.BLOCK
    assert ReasonCode.RISK_POSITION_EXISTS in result.messages
