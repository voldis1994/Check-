from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from checktrader.domain.enums import Side, StrategyType
from checktrader.domain.models import LimitState, Position
from checktrader.setups.repository import SetupRepository
from checktrader.state.migrations import SCHEMA_VERSION, migrate_state
@dataclass(slots=True)
class RuntimeState:
    instance_id: str; setups: SetupRepository=field(default_factory=SetupRepository); positions: list[Position]=field(default_factory=list); limits: LimitState=field(default_factory=lambda:LimitState(datetime.now(UTC).date().isoformat()))
    def to_dict(self) -> dict[str, Any]: return {'schema_version':SCHEMA_VERSION,'instance_id':self.instance_id,'setups':self.setups.to_list(),'positions':[p.to_dict() for p in self.positions],'limits':self.limits.to_dict()}
def _pos(r: dict[str,Any]) -> Position:
    return Position(str(r['position_id']),str(r['symbol']),Side(r['side']),float(r['lot']),float(r['entry_price']),float(r['stop_loss']) if r.get('stop_loss') is not None else None,float(r['take_profit']) if r.get('take_profit') is not None else None,datetime.fromisoformat(str(r['opened_at'])),StrategyType(r['strategy']),float(r['current_price']) if r.get('current_price') is not None else None,float(r.get('profit',0.0)),int(r['magic_number']) if r.get('magic_number') is not None else None,dict(r.get('metadata',{})))
class StateStore:
    def __init__(self, path: Path) -> None: self.path=path
    def load(self, instance_id: str) -> RuntimeState:
        if not self.path.exists(): return RuntimeState(instance_id)
        data=migrate_state(json.loads(self.path.read_text(encoding='utf-8'))); lr=data.get('limits',{}); cd=lr.get('cooldown_until'); last=lr.get('last_trade_at')
        limits=LimitState(str(lr.get('trade_date',datetime.now(UTC).date().isoformat())),int(lr.get('daily_trades',0)),int(lr.get('consecutive_losses',0)),datetime.fromisoformat(str(cd)) if cd else None,datetime.fromisoformat(str(last)) if last else None)
        return RuntimeState(str(data.get('instance_id',instance_id)),SetupRepository.from_list(data.get('setups',[])),[_pos(r) for r in data.get('positions',[]) if isinstance(r,dict)],limits)
    def save(self, state: RuntimeState) -> None:
        self.path.parent.mkdir(parents=True,exist_ok=True); tmp=self.path.with_suffix(self.path.suffix+'.tmp'); tmp.write_text(json.dumps(state.to_dict(),indent=2,sort_keys=True),encoding='utf-8'); tmp.replace(self.path)
