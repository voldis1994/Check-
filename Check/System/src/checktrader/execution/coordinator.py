from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from checktrader.bridge.reader import read_acks
from checktrader.bridge.writer import write_command
from checktrader.config.models import SystemConfig
from checktrader.domain.enums import OrderAction, ReasonCode, Side, StrategyType
from checktrader.domain.models import Acknowledgement, Command, Position
from checktrader.execution.idempotency import CommandDedupe


class ExecutionCoordinator:
    def __init__(
        self,
        config: SystemConfig,
        bridge_dir: Path | None = None,
        dedupe_path: Path | None = None,
    ) -> None:
        self.config = config
        self.bridge_dir = bridge_dir
        self._dedupe_path = dedupe_path
        if dedupe_path is not None:
            self.dedupe = CommandDedupe.load(dedupe_path, config.execution.dedupe_window_seconds)
        else:
            self.dedupe = CommandDedupe(config.execution.dedupe_window_seconds)

    def execute(self, command: Command, positions: list[Position]) -> tuple[Acknowledgement, list[Position]]:
        now = datetime.now(UTC)
        if not self.dedupe.remember(command.command_id, now):
            return Acknowledgement(command.command_id, False, ReasonCode.EXECUTION_DUPLICATE_COMMAND), positions
        self._save_dedupe()

        if self.config.runtime.mode == "paper":
            return self._paper(command, positions)

        if self.bridge_dir is None:
            return Acknowledgement(command.command_id, False, ReasonCode.BRIDGE_UNAVAILABLE), positions

        write_command(self.bridge_dir, command)
        ack = self._poll_ack(command.command_id)
        if ack.accepted and command.action == OrderAction.MODIFY:
            positions = self._apply_modify_locally(command, positions)
        return ack, positions

    def _poll_ack(self, command_id: str) -> Acknowledgement:
        """Poll acknowledgements/<command_id>.json until timeout."""
        timeout = self.config.execution.ack_timeout_seconds
        deadline = time.monotonic() + timeout
        poll_interval = 0.25
        while time.monotonic() < deadline:
            if self.bridge_dir is not None:
                for ack in read_acks(self.bridge_dir):
                    if ack.command_id == command_id:
                        return ack
            time.sleep(poll_interval)
        return Acknowledgement(
            command_id,
            False,
            ReasonCode.ACK_REJECTED,
            message=f"ack timeout after {timeout:.1f}s",
        )

    def _paper(self, command: Command, positions: list[Position]) -> tuple[Acknowledgement, list[Position]]:
        p = command.payload
        if command.action == OrderAction.OPEN:
            pos = Position(
                f"PAPER-{uuid4().hex[:12]}",
                command.symbol,
                Side(str(p["side"])),
                float(p["lot"]),
                float(p["entry_price"]),
                float(p["stop_loss"]) if p.get("stop_loss") is not None else None,
                float(p["take_profit"]) if p.get("take_profit") is not None else None,
                datetime.now(UTC),
                StrategyType(str(p["strategy"])),
                magic_number=int(p["magic_number"]) if p.get("magic_number") is not None else None,
            )
            return Acknowledgement(command.command_id, True, ReasonCode.EXECUTION_PAPER_FILLED, pos.position_id), [
                *positions,
                pos,
            ]
        if command.action == OrderAction.MODIFY:
            for pos in positions:
                if pos.position_id == p.get("position_id"):
                    if p.get("stop_loss") is not None:
                        pos.stop_loss = float(p["stop_loss"])
                    if p.get("take_profit") is not None:
                        pos.take_profit = float(p["take_profit"])
            return Acknowledgement(command.command_id, True, ReasonCode.EXECUTION_PAPER_FILLED), positions
        if command.action == OrderAction.CLOSE:
            return Acknowledgement(command.command_id, True, ReasonCode.EXECUTION_PAPER_FILLED), [
                pos for pos in positions if pos.position_id != p.get("position_id")
            ]
        return Acknowledgement(command.command_id, False, ReasonCode.ACK_REJECTED), positions

    def _apply_modify_locally(self, command: Command, positions: list[Position]) -> list[Position]:
        """Keep local SL/TP in sync after broker ACK so trailing can ratchet next cycle."""
        p = command.payload
        pid = p.get("position_id")
        for pos in positions:
            if pos.position_id != pid:
                continue
            if p.get("stop_loss") is not None:
                pos.stop_loss = float(p["stop_loss"])
            if p.get("take_profit") is not None:
                pos.take_profit = float(p["take_profit"])
            break
        return positions

    def _save_dedupe(self) -> None:
        if self._dedupe_path is not None:
            self.dedupe.save(self._dedupe_path)
