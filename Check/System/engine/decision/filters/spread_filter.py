from __future__ import annotations
from dataclasses import dataclass
from engine.decision.reason import build_reason
from engine.protocol.constants import REASON_SPREAD_ABNORMAL

@dataclass(frozen=True)
class SpreadFilterResult:
    spread_acceptable: bool
    relative_spread: float
    threshold: float
    reason: str | None

def evaluate_spread_filter(relative_spread: float, threshold: float) -> SpreadFilterResult:
    spread_acceptable = relative_spread <= threshold
    reason: str | None = None
    if not spread_acceptable:
        reason = build_reason(REASON_SPREAD_ABNORMAL, 'relative spread above threshold', relative_spread=relative_spread, threshold=threshold)
    return SpreadFilterResult(spread_acceptable=spread_acceptable, relative_spread=relative_spread, threshold=threshold, reason=reason)
