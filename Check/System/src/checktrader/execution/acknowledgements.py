from __future__ import annotations
from typing import Any
from checktrader.domain.enums import ReasonCode
from checktrader.domain.models import Acknowledgement

def parse_ack(data: dict[str, Any]) -> Acknowledgement:
    p=data.get('payload',data); p=p if isinstance(p,dict) else {}; accepted=bool(p.get('accepted',False)); default=ReasonCode.ACK_ACCEPTED if accepted else ReasonCode.ACK_REJECTED
    return Acknowledgement(str(p.get('command_id','')),accepted,ReasonCode(p.get('reason',default.value)),str(p['broker_order_id']) if p.get('broker_order_id') is not None else None,str(p.get('message','')),payload=p)
