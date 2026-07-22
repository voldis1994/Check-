from __future__ import annotations

from datetime import datetime

from checktrader.domain.enums import SetupState
from checktrader.domain.models import Setup
from checktrader.setups.state_machine import transition


def expire_setups(setups: list[Setup], current_bar_time: datetime) -> list[Setup]:
    """Expire any IDLE or ARMED setups whose expiry time has passed."""
    expired: list[Setup] = []
    for s in setups:
        armed = s.state in {SetupState.IDLE, SetupState.ARMED}
        due = s.expires_at_bar is not None and current_bar_time >= s.expires_at_bar
        if armed and due:
            transition(s, SetupState.EXPIRED)
            expired.append(s)
    return expired
