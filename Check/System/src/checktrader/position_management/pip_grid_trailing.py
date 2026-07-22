"""Discrete ATR-grid trailing after confirmed BE.

Legacy module name retained as a thin re-export for imports that still
reference pip_grid_trailing; production code uses atr_grid_trailing.
"""

from __future__ import annotations

from checktrader.position_management.atr_grid_trailing import (  # noqa: F401
    atr_step_price,
    compute_grid_stop_loss,
    count_jump_steps,
    distance_stop_loss,
    favorable_price_move,
    snap_to_reached_grid,
)

__all__ = [
    "atr_step_price",
    "compute_grid_stop_loss",
    "count_jump_steps",
    "distance_stop_loss",
    "favorable_price_move",
    "snap_to_reached_grid",
]
