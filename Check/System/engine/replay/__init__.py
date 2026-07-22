"""Stateful historical replay (no MT4 / no live execution)."""
from __future__ import annotations

from engine.replay.context import build_replay_universe, detect_session, detect_regime_from_bars
from engine.replay.execution_model import ReplayExecutionConfig, default_replay_execution_config
from engine.replay.simulator import ReplaySimulator, run_replay

__all__ = [
    'ReplayExecutionConfig',
    'ReplaySimulator',
    'build_replay_universe',
    'default_replay_execution_config',
    'detect_regime_from_bars',
    'detect_session',
    'run_replay',
]
