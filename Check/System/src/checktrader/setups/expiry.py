from __future__ import annotations
from datetime import datetime
from checktrader.domain.enums import SetupState
from checktrader.domain.models import Setup
from checktrader.setups.state_machine import transition

def expire_setups(setups: list[Setup], current_bar_time: datetime) -> list[Setup]:
    return [transition(s, SetupState.EXPIRED) for s in setups if s.expires_at_bar is not None and current_bar_time >= s.expires_at_bar]
