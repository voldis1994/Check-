from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from engine.core.atomic_io import atomic_read_text
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.protocol.errors import ValidationError
from engine.protocol.parser import parse_json
MODULE_NAME = 'loader.closed_trade'

@dataclass(frozen=True)
class ClosedTradeRecord:
    account_id: str
    symbol: str
    magic: int
    ticket: int
    close_price: float
    close_time_utc: str
    profit: float
    commission: float
    swap: float
    close_reason: str | None = None

def build_closed_trade_path(paths: SystemPaths, instance: Instance) -> Path:
    return paths.account_dir(instance.account_id) / f'closed_{instance.symbol}_{instance.magic}.json'

def _require_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f'{field} must be a number', module=MODULE_NAME, context={'value': value})
    return float(value)

def parse_closed_trade_payload(payload: dict[str, Any]) -> ClosedTradeRecord:
    ticket = payload.get('ticket')
    if not isinstance(ticket, int) or isinstance(ticket, bool):
        raise ValidationError('closed trade ticket must be an int', module=MODULE_NAME, context={'value': ticket})
    close_time = payload.get('close_time_utc')
    if not isinstance(close_time, str) or not close_time.strip():
        raise ValidationError('closed trade close_time_utc must be a non-empty string', module=MODULE_NAME, context={'value': close_time})
    close_reason = payload.get('close_reason')
    return ClosedTradeRecord(
        account_id=str(payload.get('account_id', '')),
        symbol=str(payload.get('symbol', '')),
        magic=int(payload.get('magic', 0)),
        ticket=ticket,
        close_price=_require_number(payload.get('close_price'), 'close_price'),
        close_time_utc=close_time,
        profit=_require_number(payload.get('profit', 0.0), 'profit'),
        commission=_require_number(payload.get('commission', 0.0), 'commission'),
        swap=_require_number(payload.get('swap', 0.0), 'swap'),
        close_reason=str(close_reason) if close_reason is not None else None,
    )

def load_closed_trade(paths: SystemPaths, instance: Instance) -> ClosedTradeRecord | None:
    path = build_closed_trade_path(paths, instance)
    if not path.exists():
        return None
    try:
        payload = parse_json(atomic_read_text(path))
        if not isinstance(payload, dict):
            return None
        return parse_closed_trade_payload(payload)
    except (OSError, ValidationError, ValueError, TypeError):
        return None

def find_closed_trade_for_ticket(paths: SystemPaths, instance: Instance, *, ticket: int) -> ClosedTradeRecord | None:
    record = load_closed_trade(paths, instance)
    if record is None or record.ticket != ticket:
        return None
    return record
