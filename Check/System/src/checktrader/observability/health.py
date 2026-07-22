from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from checktrader.domain.enums import ReasonCode
from checktrader.domain.models import utc_now
@dataclass(slots=True)
class HealthStatus:
    healthy: bool; timestamp: datetime=field(default_factory=utc_now); reasons: list[ReasonCode]=field(default_factory=list)
    def to_dict(self) -> dict[str,object]: return {'healthy':self.healthy,'timestamp':self.timestamp.isoformat(),'reasons':[r.value for r in self.reasons]}
def health_from_reasons(reasons: list[ReasonCode]) -> HealthStatus:
    bad={ReasonCode.MARKET_DATA_MISSING,ReasonCode.MARKET_DATA_STALE,ReasonCode.BRIDGE_UNAVAILABLE,ReasonCode.HEARTBEAT_STALE}; return HealthStatus(not any(r in bad for r in reasons),reasons=reasons)
