from __future__ import annotations

from engine.core.instance import Instance
from engine.protocol.constants import (
    REASON_ACCOUNT_NOT_TRADEABLE,
    REASON_RISK_DAILY_LOSS,
    REASON_RISK_MAX_DRAWDOWN,
    REASON_RISK_MAX_POSITIONS,
)
from engine.protocol.models import RiskConfig, StatusRecord
from engine.risk.rules import (
    RiskContext,
    RiskRuleResult,
    check_max_daily_loss,
    check_max_drawdown,
    check_max_open_positions,
    check_trade_allowed,
    evaluate_risk_rules,
    open_position_count,
)
from engine.state.instance_state import InstanceState


def _risk_config() -> RiskConfig:
    return RiskConfig(
        max_open_positions_per_instance=1,
        max_daily_loss_percent=2.0,
        max_drawdown_percent=10.0,
        reward_ratio=2.0,
        max_risk_per_trade_percent=1.0,
        max_stop_loss_pips=100.0,
        volume_step=0.01,
    )


def _status(*, trade_allowed: bool = True) -> StatusRecord:
    return StatusRecord(
        schema_version="1.0.0",
        timestamp_utc="2026-07-07T06:00:00.000Z",
        account_id="12345",
        connected=True,
        trade_allowed=trade_allowed,
        balance=10000.0,
        equity=10000.0,
        margin_free=9000.0,
        ea_version="1.0.0",
    )


def _instance_state(*, with_position: bool = False) -> InstanceState:
    state = InstanceState(instance=Instance(account_id="12345", symbol="EURUSD", magic=100001))
    if with_position:
        state.update_position(open_ticket=1001, position_side="BUY", position_volume=0.1)
    return state


def _risk_context(
    *,
    daily_loss_percent: float = 0.0,
    drawdown_percent: float = 0.0,
) -> RiskContext:
    return RiskContext(
        daily_loss_percent=daily_loss_percent,
        drawdown_percent=drawdown_percent,
    )


def test_open_position_count_reflects_instance_state() -> None:
    assert open_position_count(_instance_state(with_position=False)) == 0
    assert open_position_count(_instance_state(with_position=True)) == 1


def test_check_max_open_positions_blocks_when_limit_reached() -> None:
    allowed = check_max_open_positions(
        instance_state=_instance_state(with_position=False),
        risk_config=_risk_config(),
    )
    blocked = check_max_open_positions(
        instance_state=_instance_state(with_position=True),
        risk_config=_risk_config(),
    )

    assert allowed.allowed
    assert allowed.reason is None
    assert not blocked.allowed
    assert blocked.reason is not None
    assert REASON_RISK_MAX_POSITIONS in blocked.reason


def test_check_max_daily_loss_blocks_at_limit() -> None:
    allowed = check_max_daily_loss(risk_config=_risk_config(), daily_loss_percent=1.5)
    blocked = check_max_daily_loss(risk_config=_risk_config(), daily_loss_percent=2.0)

    assert allowed.allowed
    assert not blocked.allowed
    assert blocked.reason is not None
    assert REASON_RISK_DAILY_LOSS in blocked.reason


def test_check_max_drawdown_blocks_at_limit() -> None:
    allowed = check_max_drawdown(risk_config=_risk_config(), drawdown_percent=8.0)
    blocked = check_max_drawdown(risk_config=_risk_config(), drawdown_percent=10.0)

    assert allowed.allowed
    assert not blocked.allowed
    assert blocked.reason is not None
    assert REASON_RISK_MAX_DRAWDOWN in blocked.reason


def test_check_trade_allowed_blocks_when_false() -> None:
    allowed = check_trade_allowed(status=_status(trade_allowed=True))
    blocked = check_trade_allowed(status=_status(trade_allowed=False))

    assert allowed.allowed
    assert not blocked.allowed
    assert blocked.reason is not None
    assert REASON_ACCOUNT_NOT_TRADEABLE in blocked.reason


def test_evaluate_risk_rules_returns_first_block_reason() -> None:
    result = evaluate_risk_rules(
        status=_status(trade_allowed=False),
        instance_state=_instance_state(with_position=True),
        risk_config=_risk_config(),
        risk_context=_risk_context(daily_loss_percent=5.0, drawdown_percent=15.0),
    )

    assert isinstance(result, RiskRuleResult)
    assert not result.allowed
    assert result.reason is not None
    assert REASON_ACCOUNT_NOT_TRADEABLE in result.reason


def test_evaluate_risk_rules_allows_when_all_checks_pass() -> None:
    result = evaluate_risk_rules(
        status=_status(trade_allowed=True),
        instance_state=_instance_state(with_position=False),
        risk_config=_risk_config(),
        risk_context=_risk_context(daily_loss_percent=0.5, drawdown_percent=3.0),
    )

    assert result.allowed
    assert result.reason is None


def test_every_blocked_rule_includes_reason() -> None:
    blocked_results = [
        check_trade_allowed(status=_status(trade_allowed=False)),
        check_max_open_positions(
            instance_state=_instance_state(with_position=True),
            risk_config=_risk_config(),
        ),
        check_max_daily_loss(risk_config=_risk_config(), daily_loss_percent=3.0),
        check_max_drawdown(risk_config=_risk_config(), drawdown_percent=12.0),
    ]

    for result in blocked_results:
        assert not result.allowed
        assert result.reason is not None
        assert ":" in result.reason
