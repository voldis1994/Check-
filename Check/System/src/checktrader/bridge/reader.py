from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from checktrader.bridge.atomic_files import read_json
from checktrader.domain.enums import ReasonCode, Side, StrategyType
from checktrader.domain.models import AccountStatus, Acknowledgement, Candle, MarketSnapshot, Position

def _payload(data: dict[str,Any]|None) -> dict[str,Any]|None:
    if data is None: return None
    p=data.get('payload',data); return p if isinstance(p,dict) else None
def read_market(bridge_dir: Path, default_symbol: str) -> MarketSnapshot|None:
    p=_payload(read_json(bridge_dir/'market.json'))
    if p is None: return None
    ts=p.get('timestamp') or p.get('time'); t=datetime.fromisoformat(str(ts).replace('Z','+00:00')) if ts else datetime.now(UTC); candles=p.get('candles',{}) if isinstance(p.get('candles',{}),dict) else {}
    bid=float(p.get('bid',p.get('close',0.0))); ask=float(p.get('ask',bid)); symbol=str(p.get('symbol',default_symbol))
    return MarketSnapshot(symbol,bid,ask,t,[Candle.from_dict(r,'M1') for r in candles.get('M1',p.get('m1',[])) if isinstance(r,dict)],[Candle.from_dict(r,'M5') for r in candles.get('M5',p.get('m5',[])) if isinstance(r,dict)],[Candle.from_dict(r,'M15') for r in candles.get('M15',p.get('m15',[])) if isinstance(r,dict)],heartbeat_at=t)
def read_status(bridge_dir: Path) -> AccountStatus|None:
    p=_payload(read_json(bridge_dir/'status.json'))
    return None if p is None else AccountStatus(str(p.get('account_id',p.get('login',''))),float(p.get('balance',0.0)),float(p.get('equity',p.get('balance',0.0))),float(p.get('margin_free',p.get('free_margin',0.0))),str(p.get('currency','USD')),bool(p.get('trading_allowed',True)),bool(p.get('connected',True)))
def read_positions(bridge_dir: Path) -> list[Position]:
    p=_payload(read_json(bridge_dir/'positions.json')); rows=[] if p is None else p.get('positions',[]); out=[]
    for r in rows if isinstance(rows,list) else []:
        if not isinstance(r,dict): continue
        opened=r.get('opened_at') or r.get('open_time'); opened_at=datetime.fromisoformat(str(opened).replace('Z','+00:00')) if opened else datetime.now(UTC)
        side=Side.SHORT if str(r.get('side','LONG')).upper() in {'SHORT','SELL'} else Side.LONG
        out.append(Position(str(r.get('position_id',r.get('ticket',''))),str(r.get('symbol','')),side,float(r.get('lot',r.get('lots',0.0))),float(r.get('entry_price',r.get('open_price',0.0))),float(r['stop_loss']) if r.get('stop_loss') is not None else None,float(r['take_profit']) if r.get('take_profit') is not None else None,opened_at,StrategyType(r.get('strategy','TREND_CONTINUATION')),float(r['current_price']) if r.get('current_price') is not None else None,float(r.get('profit',0.0)),int(r['magic_number']) if r.get('magic_number') is not None else None))
    return out
def read_acks(bridge_dir: Path) -> list[Acknowledgement]:
    p=_payload(read_json(bridge_dir/'acks.json')); rows=[] if p is None else p.get('acks',[]); out=[]
    for r in rows if isinstance(rows,list) else []:
        if isinstance(r,dict):
            accepted=bool(r.get('accepted',False)); default='ACK_ACCEPTED' if accepted else 'ACK_REJECTED'; out.append(Acknowledgement(str(r.get('command_id','')),accepted,ReasonCode(r.get('reason',default)),str(r['broker_order_id']) if r.get('broker_order_id') is not None else None,str(r.get('message','')),payload=r))
    return out
