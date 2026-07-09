from __future__ import annotations
from dataclasses import dataclass
from engine.decision.buy import BuyCandidate
from engine.decision.reason import build_reason
from engine.decision.scorer import ScoringResult
from engine.decision.sell import SellCandidate
from engine.protocol.constants import REASON_BOTH_DIRECTIONS_INVALID, REASON_EQUAL_SCORES, REASON_EXECUTION_NOT_POSSIBLE, Side, is_block_reason_code

@dataclass(frozen=True)
class WaitDecisionResult:
    is_wait: bool
    reason: str | None

@dataclass(frozen=True)
class BlockDecisionResult:
    is_block: bool
    reason: str | None

def _extract_reason_code(reason: str) -> str:
    return reason.split(':', 1)[0].strip()

def build_both_directions_invalid_reason(buy_candidate: BuyCandidate, sell_candidate: SellCandidate) -> str:
    return build_reason(REASON_BOTH_DIRECTIONS_INVALID, 'neither buy nor sell setup is valid', buy_invalid_reason=buy_candidate.invalid_reason, sell_invalid_reason=sell_candidate.invalid_reason)

def evaluate_wait_decision(*, buy_candidate: BuyCandidate, sell_candidate: SellCandidate, scoring: ScoringResult, execution_possible: bool=True) -> WaitDecisionResult:
    if not buy_candidate.valid and (not sell_candidate.valid):
        return WaitDecisionResult(is_wait=True, reason=build_both_directions_invalid_reason(buy_candidate, sell_candidate))
    if buy_candidate.valid and sell_candidate.valid and (scoring.preferred_side == Side.NONE.value):
        return WaitDecisionResult(is_wait=True, reason=build_reason(REASON_EQUAL_SCORES, 'buy and sell scores are equal', buy_score=scoring.buy_score, sell_score=scoring.sell_score))
    if scoring.preferred_side in {Side.BUY.value, Side.SELL.value} and (not execution_possible):
        return WaitDecisionResult(is_wait=True, reason=build_reason(REASON_EXECUTION_NOT_POSSIBLE, 'execution is not possible for preferred side', preferred_side=scoring.preferred_side))
    return WaitDecisionResult(is_wait=False, reason=None)

def evaluate_block_decision(*, block_reason: str | None) -> BlockDecisionResult:
    if block_reason is None or not block_reason.strip():
        return BlockDecisionResult(is_block=False, reason=None)
    reason_code = _extract_reason_code(block_reason)
    if not is_block_reason_code(reason_code):
        return BlockDecisionResult(is_block=False, reason=None)
    return BlockDecisionResult(is_block=True, reason=block_reason.strip())
