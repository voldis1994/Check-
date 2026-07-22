"""Setup state machine tests."""

from __future__ import annotations

from datetime import UTC, datetime

from checktrader.domain.enums import ReasonCode, SetupState, Side, StrategyType
from checktrader.domain.models import Setup
from checktrader.setups.state_machine import TERMINAL_STATES, transition


def test_armed_to_triggered_to_open() -> None:
    setup = Setup.create(
        symbol="TEST",
        strategy=StrategyType.TREND_CONTINUATION,
        side=Side.BUY,
        state=SetupState.ARMED,
        created_at_bar=datetime(2026, 1, 1, tzinfo=UTC),
        expires_at_bar=None,
        trigger_price=1.1,
        stop_loss=1.0,
        take_profit=1.3,
        reason=ReasonCode.SETUP_CREATED,
    )
    setup = transition(setup, SetupState.TRIGGERED)
    assert setup.state is SetupState.TRIGGERED
    setup = transition(setup, SetupState.ORDER_PENDING)
    setup = transition(setup, SetupState.OPEN)
    assert setup.state is SetupState.OPEN


def test_terminal_states() -> None:
    assert SetupState.EXPIRED in TERMINAL_STATES
    assert SetupState.CANCELLED in TERMINAL_STATES
    assert SetupState.ARMED not in TERMINAL_STATES
