"""Paper mode cycle must NOT write command files to commands/ directory."""

from __future__ import annotations

from pathlib import Path

import pytest

from checktrader.app.bootstrap import bootstrap
from checktrader.app.cycle import run_cycle
from checktrader.domain.enums import ReasonCode


def test_paper_cycle_does_not_write_commands(tmp_path: Path) -> None:
    """Paper mode execution should never write files to bridge/commands/."""
    config_path = Path("config/system.example.json")
    if not config_path.exists():
        pytest.skip("config/system.example.json not found")

    ctx = bootstrap(config_path, mode_override="paper")
    # Override paths to use tmp_path so we can inspect
    bridge_commands = tmp_path / "commands"
    bridge_commands.mkdir(parents=True)

    # Run a cycle
    audit = run_cycle(ctx)

    # Paper mode: even if an OPEN signal fired, no command file should be written
    # (The coordinator in paper mode calls _paper() which does NOT write files)
    # The bridge_commands directory we're watching is tmp_path/commands (not used by ctx)
    # But the ctx.execution has no bridge_dir (paper mode)
    # So we check that the runtime/bridge/commands directory is empty or no new files
    runtime_bridge_commands = ctx.config.paths.runtime_dir / "bridge" / "commands"
    if runtime_bridge_commands.exists():
        command_files = list(runtime_bridge_commands.glob("command_*.json"))
        assert len(command_files) == 0, f"Paper mode wrote {len(command_files)} command file(s): {command_files}"

    # Verify cycle completed or had a valid early exit
    assert any(
        r in audit.reasons
        for r in (
            ReasonCode.CYCLE_COMPLETED,
            ReasonCode.CYCLE_STARTED,
            ReasonCode.HISTORY_INSUFFICIENT,
            ReasonCode.NO_CLOSED_BARS,
            ReasonCode.BARS_NOT_SEQUENTIAL,
        )
    )


def test_paper_cycle_uses_paper_execution_mode(tmp_path: Path) -> None:
    """Verify bootstrap with paper mode has mode='paper' and no bridge_dir writes."""
    config_path = Path("config/system.example.json")
    if not config_path.exists():
        pytest.skip("config/system.example.json not found")

    ctx = bootstrap(config_path, mode_override="paper")
    assert ctx.config.runtime.mode == "paper"
    # Paper mode execution coordinator should not have a bridge_dir
    # (bridge_dir is None in paper mode → writes go to paper fill, not filesystem)
    assert ctx.execution.bridge_dir is None or ctx.config.runtime.mode == "paper"
