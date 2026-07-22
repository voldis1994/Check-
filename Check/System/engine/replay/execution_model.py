"""Replay execution assumptions (spread / slippage / commission / fill model)."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ReplayExecutionConfig:
    """Simulated fill model for stateful replay.

    Entry fills on the **next** closed bar's open (decision is made after the
    signal bar closes). Signal-bar close is never used as a guaranteed fill.
    """

    entry_on_next_bar_open: bool = True
    spread_price: float = 0.00010
    slippage_price: float = 0.00002
    commission_per_trade: float = 0.0
    lot_size: float = 0.01
    point_value_per_lot: float = 1.0
    # When both SL and TP are touched in the same bar without lower-TF data,
    # assume the worst outcome for the position side.
    intrabar_conflict_rule: str = 'worst_case'
    timezone_name: str = 'UTC'
    max_open_positions: int = 1


def default_replay_execution_config() -> ReplayExecutionConfig:
    return ReplayExecutionConfig()
