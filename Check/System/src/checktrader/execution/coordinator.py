from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from checktrader.bridge.writer import write_command
from checktrader.config.models import SystemConfig
from checktrader.domain.enums import OrderAction, ReasonCode, Side, StrategyType
from checktrader.domain.models import Acknowledgement, Command, Position
from checktrader.execution.idempotency import CommandDedupe
class ExecutionCoordinator:
    def __init__(self, config: SystemConfig, bridge_dir: Path|None=None) -> None: self.config=config; self.bridge_dir=bridge_dir; self.dedupe=CommandDedupe(config.execution.dedupe_window_seconds)
    def execute(self, command: Command, positions: list[Position]) -> tuple[Acknowledgement,list[Position]]:
        now=datetime.now(UTC)
        if not self.dedupe.remember(command.command_id,now): return Acknowledgement(command.command_id,False,ReasonCode.EXECUTION_DUPLICATE_COMMAND), positions
        if self.config.runtime.mode=='paper': return self._paper(command,positions)
        if self.bridge_dir is None: return Acknowledgement(command.command_id,False,ReasonCode.BRIDGE_UNAVAILABLE), positions
        write_command(self.bridge_dir,command); return Acknowledgement(command.command_id,True,ReasonCode.EXECUTION_COMMAND_WRITTEN), positions
    def _paper(self, command: Command, positions: list[Position]) -> tuple[Acknowledgement,list[Position]]:
        p=command.payload
        if command.action==OrderAction.OPEN:
            pos=Position(f'PAPER-{uuid4().hex[:12]}',command.symbol,Side(str(p['side'])),float(p['lot']),float(p['entry_price']),float(p['stop_loss']) if p.get('stop_loss') is not None else None,float(p['take_profit']) if p.get('take_profit') is not None else None,datetime.now(UTC),StrategyType(str(p['strategy'])),magic_number=int(p['magic_number']) if p.get('magic_number') is not None else None)
            return Acknowledgement(command.command_id,True,ReasonCode.EXECUTION_PAPER_FILLED,pos.position_id), [*positions,pos]
        if command.action==OrderAction.MODIFY:
            for pos in positions:
                if pos.position_id==p.get('position_id'):
                    if p.get('stop_loss') is not None: pos.stop_loss=float(p['stop_loss'])
                    if p.get('take_profit') is not None: pos.take_profit=float(p['take_profit'])
            return Acknowledgement(command.command_id,True,ReasonCode.EXECUTION_PAPER_FILLED), positions
        if command.action==OrderAction.CLOSE:
            return Acknowledgement(command.command_id,True,ReasonCode.EXECUTION_PAPER_FILLED), [pos for pos in positions if pos.position_id!=p.get('position_id')]
        return Acknowledgement(command.command_id,False,ReasonCode.ACK_REJECTED), positions
