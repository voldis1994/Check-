"""Acceptance: fixed_lot=0.01 only, ATR distances, no risk blockers in production."""

from __future__ import annotations

import ast
from pathlib import Path

from checktrader.config.models import PositionSizingConfig, SystemConfig
from checktrader.domain.enums import RiskDecision, Side
from checktrader.domain.money import SymbolSpecs, money_per_price_unit
from checktrader.position_management.atr_grid_trailing import atr_step_price
from checktrader.position_management.breakeven import calculate_be_stop_loss
from checktrader.risk.broker_constraints import round_price_to_tick
from checktrader.risk.engine import approve_order
from checktrader.risk.stop_loss import atr_to_price_distance
from tests.fixtures.helpers import EURUSD_SPECS, load_test_config

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "checktrader"

_FORBIDDEN_RISK_TOKENS = (
    "risk_percent",
    "DAILY_LOSS_LIMIT",
    "DRAWDOWN_LIMIT",
    "RISK_PERCENT_EXCEEDED",
    "MAX_CONSECUTIVE_LOSSES",
    "LOSS_COOLDOWN",
    "TRADE_COOLDOWN",
    "martingale",
    "anti_martingale",
    "daily_loss_limit",
    "drawdown_limit",
)


def _approve(
    *,
    specs: SymbolSpecs = EURUSD_SPECS,
    lot: float = 0.01,
    atr: float = 0.001,
    stop_loss: float = 1.09800,
    free_margin: float = 5_000,
) -> object:
    return approve_order(
        side=Side.BUY,
        entry=1.10000,
        stop_loss=stop_loss,
        specs=specs,
        sizing=PositionSizingConfig(fixed_lot=lot),
        atr=atr,
        maximum_stop_atr=2.5,
        free_margin=free_margin,
        broker_server="Demo-Server",
    )


def test_01_open_uses_exactly_001() -> None:
    assert _approve().volume == 0.01  # type: ignore[attr-defined]


def test_02_equity_change_does_not_change_lot() -> None:
    # equity is not an input; free_margin change must not resize
    assert _approve(free_margin=100).volume == _approve(free_margin=100_000).volume == 0.01  # type: ignore[attr-defined]


def test_03_sl_distance_does_not_change_lot() -> None:
    assert _approve(stop_loss=1.09950).volume == _approve(stop_loss=1.09800).volume == 0.01  # type: ignore[attr-defined]


def test_04_atr_change_does_not_change_lot() -> None:
    assert _approve(atr=0.0005).volume == _approve(atr=0.005).volume == 0.01  # type: ignore[attr-defined]


def test_05_loss_series_has_no_lot_api() -> None:
    import inspect

    assert "consecutive" not in inspect.signature(approve_order).parameters
    assert "loss" not in inspect.signature(approve_order).parameters


def test_06_daily_result_has_no_lot_api() -> None:
    import inspect

    params = inspect.signature(approve_order).parameters
    assert "equity" not in params
    assert "daily" not in params
    assert "pnl" not in params


def test_07_broker_min_lot_001_allows() -> None:
    assert _approve().decision is RiskDecision.APPROVED  # type: ignore[attr-defined]


def test_08_broker_min_lot_010_rejects() -> None:
    specs = SymbolSpecs(
        symbol="EURUSD",
        digits=5,
        point=0.00001,
        pip_size=0.0001,
        tick_size=0.00001,
        tick_value=1.0,
        minimum_lot=0.10,
        maximum_lot=100.0,
        lot_step=0.10,
        stop_level_points=0,
        freeze_level_points=0,
    )
    r = _approve(specs=specs)
    assert r.decision is RiskDecision.FIXED_LOT_NOT_SUPPORTED  # type: ignore[attr-defined]
    assert r.volume == 0.0  # type: ignore[attr-defined]


def test_09_lot_step_001_valid() -> None:
    assert _approve().decision is RiskDecision.APPROVED  # type: ignore[attr-defined]


def test_10_lot_step_010_rejects_001() -> None:
    specs = SymbolSpecs(
        symbol="EURUSD",
        digits=5,
        point=0.00001,
        pip_size=0.0001,
        tick_size=0.00001,
        tick_value=1.0,
        minimum_lot=0.01,
        maximum_lot=100.0,
        lot_step=0.10,
        stop_level_points=0,
        freeze_level_points=0,
    )
    r = _approve(specs=specs)
    assert r.decision is RiskDecision.FIXED_LOT_NOT_SUPPORTED  # type: ignore[attr-defined]


def test_11_margin_insufficient_rejects_without_resize() -> None:
    r = _approve(free_margin=0.0)
    assert r.decision is RiskDecision.MARGIN_INSUFFICIENT_FOR_FIXED_LOT  # type: ignore[attr-defined]
    assert r.volume == 0.0  # type: ignore[attr-defined]
    assert r.requested_lot == 0.01  # type: ignore[attr-defined]


def test_12_never_auto_change_lot() -> None:
    specs = SymbolSpecs(
        symbol="XAUUSD",
        digits=2,
        point=0.01,
        pip_size=0.01,
        tick_size=0.01,
        tick_value=1.0,
        minimum_lot=0.10,
        maximum_lot=50.0,
        lot_step=0.10,
        stop_level_points=0,
        freeze_level_points=0,
    )
    r = _approve(specs=specs, stop_loss=1.09)
    # invalid stop distance for gold-like but lot rejection may fire first on min lot
    assert r.volume == 0.0  # type: ignore[attr-defined]
    assert r.requested_lot == 0.01  # type: ignore[attr-defined]


def test_13_natural_gas_tick_size_rounding() -> None:
    ng = SymbolSpecs(
        symbol="NGAS",
        digits=3,
        point=0.001,
        pip_size=0.001,
        tick_size=0.001,
        tick_value=10.0,
        minimum_lot=0.01,
        maximum_lot=100.0,
        lot_step=0.01,
        stop_level_points=0,
        freeze_level_points=0,
    )
    dist = atr_to_price_distance(0.050, 0.20, ng)
    assert dist == round_price_to_tick(0.010, ng.tick_size)
    assert dist == 0.010


def test_14_forex_tick_size_rounding() -> None:
    dist = atr_to_price_distance(0.00123, 0.20, EURUSD_SPECS)
    assert abs(dist / EURUSD_SPECS.tick_size - round(dist / EURUSD_SPECS.tick_size)) < 1e-9


def test_15_be_uses_001_and_tick_value() -> None:
    be, _ = calculate_be_stop_loss(
        side=Side.BUY,
        open_price=1.10000,
        volume=0.01,
        specs=EURUSD_SPECS,
        be_net_profit_money=0.20,
        swap=0.0,
        commission=0.0,
    )
    mppu = money_per_price_unit(tick_value=1.0, tick_size=0.00001, volume=0.01)
    expected = 1.10000 + 0.20 / mppu
    assert be is not None
    assert abs(be - expected) < 1e-8


def test_16_atr_trailing_digits_and_tick() -> None:
    step = atr_step_price(atr=0.050, trailing_step_atr=0.20, specs=EURUSD_SPECS)
    assert step == 0.010
    jpy = SymbolSpecs(
        symbol="USDJPY",
        digits=3,
        point=0.001,
        pip_size=0.01,
        tick_size=0.001,
        tick_value=1.0,
        minimum_lot=0.01,
        maximum_lot=100.0,
        lot_step=0.01,
        stop_level_points=0,
        freeze_level_points=0,
    )
    assert atr_step_price(atr=0.050, trailing_step_atr=0.20, specs=jpy) == 0.010


def test_17_no_risk_percent_sizing_in_production() -> None:
    hits: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "risk_percent" in text:
            hits.append(str(path.relative_to(SRC_ROOT)))
    assert hits == []


def test_18_no_daily_loss_or_drawdown_blockers() -> None:
    hits: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in ("DAILY_LOSS_LIMIT", "DRAWDOWN_LIMIT", "daily_loss_limit", "drawdown_limit"):
            if token in text:
                hits.append(f"{path.name}:{token}")
    assert hits == []


def test_19_no_cooldown_after_trade_or_loss() -> None:
    hits: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in ("LOSS_COOLDOWN", "TRADE_COOLDOWN", "cooldown"):
            if token in text:
                hits.append(f"{path.name}:{token}")
    assert hits == []


def test_20_config_is_fixed_lot_only() -> None:
    config = load_test_config()
    assert config.position_sizing.mode == "fixed_lot"
    assert config.position_sizing.fixed_lot == 0.01
    assert config.position_sizing.allow_broker_lot_normalization is False
    assert config.trade_management.be_activation_r is None
    # Production model rejects risk_percent
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SystemConfig.model_validate(
            {
                **SystemConfig().model_dump(),
                "position_sizing": {"mode": "risk_percent", "fixed_lot": 0.01},
            }
        )


def test_forbidden_tokens_not_in_ast_names() -> None:
    """Secondary scan: forbidden identifiers absent from production AST names."""
    found: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in _FORBIDDEN_RISK_TOKENS:
                found.append(node.id)
            if isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_RISK_TOKENS:
                found.append(node.attr)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in _FORBIDDEN_RISK_TOKENS:
                found.append(node.value)
    assert found == []
