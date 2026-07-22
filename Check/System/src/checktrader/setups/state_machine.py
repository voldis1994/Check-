from __future__ import annotations

from checktrader.domain.enums import ReasonCode, SetupState
from checktrader.domain.models import Setup, utc_now

# Valid transitions: from_state -> {allowed to_states}
_ALLOWED: dict[SetupState, set[SetupState]] = {
    SetupState.IDLE: {
        SetupState.ARMED,
        SetupState.CANCELLED,
        SetupState.EXPIRED,
    },
    SetupState.ARMED: {
        SetupState.TRIGGERED,
        SetupState.CANCELLED,
        SetupState.EXPIRED,
    },
    SetupState.TRIGGERED: {
        SetupState.ORDER_PENDING,
        SetupState.CANCELLED,
    },
    SetupState.ORDER_PENDING: {
        SetupState.OPEN,
        SetupState.REJECTED,
        SetupState.CANCELLED,
    },
    SetupState.OPEN: {
        SetupState.CLOSED,
    },
    SetupState.EXPIRED: set(),
    SetupState.CANCELLED: set(),
    SetupState.REJECTED: set(),
    SetupState.CLOSED: set(),
}

_REASON: dict[SetupState, ReasonCode] = {
    SetupState.IDLE: ReasonCode.SETUP_CREATED,
    SetupState.ARMED: ReasonCode.SETUP_ARMED,
    SetupState.TRIGGERED: ReasonCode.SETUP_TRIGGERED,
    SetupState.ORDER_PENDING: ReasonCode.SETUP_ORDER_PENDING,
    SetupState.OPEN: ReasonCode.SETUP_OPEN,
    SetupState.EXPIRED: ReasonCode.SETUP_EXPIRED,
    SetupState.CANCELLED: ReasonCode.SETUP_CANCELLED,
    SetupState.REJECTED: ReasonCode.SETUP_REJECTED,
    SetupState.CLOSED: ReasonCode.SETUP_CLOSED,
}

# Terminal states — no further transitions possible
TERMINAL_STATES: frozenset[SetupState] = frozenset(
    {
        SetupState.EXPIRED,
        SetupState.CANCELLED,
        SetupState.REJECTED,
        SetupState.CLOSED,
    }
)


def transition(setup: Setup, target: SetupState) -> Setup:
    """Advance `setup` to `target` if the transition is valid; silently ignore otherwise."""
    if target in _ALLOWED.get(setup.state, set()):
        setup.state = target
        reason = _REASON[target]
        setup.reason = reason
        setup.status_history.append({"state": target.value, "reason": reason.value, "at": utc_now().isoformat()})
    return setup


def is_terminal(setup: Setup) -> bool:
    return setup.state in TERMINAL_STATES
