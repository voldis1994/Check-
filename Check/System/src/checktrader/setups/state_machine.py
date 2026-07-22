from __future__ import annotations
from checktrader.domain.enums import ReasonCode, SetupState
from checktrader.domain.models import Setup
_ALLOWED={SetupState.CANDIDATE:{SetupState.WAITING_CONFIRMATION,SetupState.READY,SetupState.CANCELLED,SetupState.EXPIRED},SetupState.WAITING_CONFIRMATION:{SetupState.READY,SetupState.CANCELLED,SetupState.EXPIRED},SetupState.READY:{SetupState.TRIGGERED,SetupState.CANCELLED,SetupState.EXPIRED},SetupState.TRIGGERED:set(),SetupState.EXPIRED:set(),SetupState.CANCELLED:set()}
_REASON={SetupState.CANDIDATE:ReasonCode.SETUP_CREATED,SetupState.WAITING_CONFIRMATION:ReasonCode.SETUP_WAITING_CONFIRMATION,SetupState.READY:ReasonCode.SETUP_CONFIRMED,SetupState.TRIGGERED:ReasonCode.SETUP_TRIGGERED,SetupState.EXPIRED:ReasonCode.SETUP_EXPIRED,SetupState.CANCELLED:ReasonCode.SETUP_CANCELLED}
def transition(setup: Setup, target: SetupState) -> Setup:
    if target in _ALLOWED[setup.state]: setup.state=target; setup.reason=_REASON[target]
    return setup
