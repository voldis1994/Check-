"""Live mode with missing bridge returns BRIDGE_UNAVAILABLE — no OPEN signals sent."""

from __future__ import annotations

from pathlib import Path

from checktrader.config.loader import load_config
from checktrader.domain.enums import ReasonCode, Side, StrategyType
from checktrader.domain.models import StrategySignal
from checktrader.execution.commands import build_open
from checktrader.execution.coordinator import ExecutionCoordinator

# ── Coordinator-level test: live mode, no bridge_dir ──────────────────────────


def _make_signal() -> StrategySignal:
    return StrategySignal(
        strategy=StrategyType.TREND_CONTINUATION,
        side=Side.BUY,
        symbol="EURUSD",
        entry_price=1.1000,
        stop_loss=1.0950,
        take_profit=1.1100,
        reason=ReasonCode.TREND_BUY_SIGNAL,
    )


def test_live_coordinator_no_bridge_returns_unavailable() -> None:
    """ExecutionCoordinator in live mode with bridge_dir=None returns BRIDGE_UNAVAILABLE."""
    cfg = load_config()
    # Switch to live mode via model_copy
    live_rt = cfg.runtime.model_copy(update={"mode": "live", "trading_enabled": True})
    live_cfg = cfg.model_copy(update={"runtime": live_rt})

    coord = ExecutionCoordinator(live_cfg, bridge_dir=None)
    signal = _make_signal()
    cmd = build_open(signal, 0.01, live_cfg.execution)
    ack, positions = coord.execute(cmd, [])
    assert ack.reason == ReasonCode.BRIDGE_UNAVAILABLE
    assert ack.accepted is False
    assert positions == []


def test_live_coordinator_no_open_without_bridge() -> None:
    """Live mode with no bridge: OPEN commands are never written."""
    cfg = load_config()
    live_rt = cfg.runtime.model_copy(update={"mode": "live", "trading_enabled": True})
    live_cfg = cfg.model_copy(update={"runtime": live_rt})

    coord = ExecutionCoordinator(live_cfg, bridge_dir=None)
    signal = _make_signal()
    cmd = build_open(signal, 0.01, live_cfg.execution)
    ack, positions = coord.execute(cmd, [])
    # Should be unavailable, not executed
    assert ack.reason in {ReasonCode.BRIDGE_UNAVAILABLE, ReasonCode.EXECUTION_DUPLICATE_COMMAND}
    assert len(positions) == 0


def test_live_coordinator_with_bridge_writes_command(tmp_path: Path) -> None:
    """Live mode WITH a bridge_dir writes the command file (then times out on ack)."""
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir(parents=True)

    cfg = load_config()
    live_rt = cfg.runtime.model_copy(update={"mode": "live", "trading_enabled": True})
    # Reduce ack timeout so test doesn't wait long
    exec_cfg = cfg.execution.model_copy(update={"ack_timeout_seconds": 0.1})
    live_cfg = cfg.model_copy(update={"runtime": live_rt, "execution": exec_cfg})

    coord = ExecutionCoordinator(live_cfg, bridge_dir=bridge_dir)
    signal = _make_signal()
    cmd = build_open(signal, 0.01, live_cfg.execution)
    ack, positions = coord.execute(cmd, [])
    # Command file should have been written, even if ack timed out
    commands_dir = bridge_dir / "commands"
    assert commands_dir.exists()
    command_files = list(commands_dir.glob("command_*.json"))
    assert len(command_files) == 1
    # ACK may be ACK_REJECTED (timeout) since no MT4 bridge is responding
    assert ack.command_id == cmd.command_id


def test_paper_coordinator_does_not_write_files(tmp_path: Path) -> None:
    """Paper mode ExecutionCoordinator NEVER writes command files."""
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir(parents=True)

    cfg = load_config()
    # Paper mode — bridge_dir should be ignored
    coord = ExecutionCoordinator(cfg, bridge_dir=bridge_dir)
    assert cfg.runtime.mode == "paper"

    signal = _make_signal()
    cmd = build_open(signal, 0.01, cfg.execution)
    ack, positions = coord.execute(cmd, [])
    # Should be PAPER_FILLED, not COMMAND_WRITTEN
    assert ack.reason == ReasonCode.EXECUTION_PAPER_FILLED
    # No command files should be written
    commands_dir = bridge_dir / "commands"
    if commands_dir.exists():
        assert list(commands_dir.glob("command_*.json")) == []
