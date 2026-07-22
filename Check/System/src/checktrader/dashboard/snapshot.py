"""Minimal dashboard snapshot."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from checktrader.state.store import InstanceRuntimeState


def build_dashboard_snapshot(state: InstanceRuntimeState) -> dict[str, Any]:
    return {
        "position_state": state.position.state.value,
        "ticket": state.position.ticket,
        "volume": state.position.volume,
        "broker_sl": state.trailing.broker_stop_loss,
        "be_confirmed": state.trailing.be_confirmed,
        "confirmed_be_sl": state.trailing.confirmed_be_sl,
        "pending_sl": state.trailing.pending_stop_loss,
        "peak_net_profit": state.trailing.peak_net_profit,
        "last_reason": state.last_reason,
        "trailing": asdict(state.trailing),
        "position_sizing_note": "fixed_lot only — lot never derived from equity/risk_percent",
    }
