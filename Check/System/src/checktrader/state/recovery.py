from __future__ import annotations

from checktrader.config.models import SystemConfig
from checktrader.state.store import RuntimeState, StateStore


def recover_state(config: SystemConfig) -> RuntimeState:
    return StateStore(config.paths.state_file).load(config.runtime.instance_id)
