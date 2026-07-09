from __future__ import annotations
from engine.decision.engine import DecisionResult
from engine.protocol.constants import Decision
from engine.protocol.models import RiskConfig, StatusRecord
from engine.risk.metrics import build_risk_context
from engine.risk.rules import evaluate_risk_rules
from engine.state.instance_state import InstanceState
MODULE_NAME = 'risk.precheck'

def should_call_ai_layer(*, decision_result: DecisionResult, status: StatusRecord, instance_state: InstanceState, risk_config: RiskConfig) -> bool:
    if decision_result.decision not in {Decision.BUY.value, Decision.SELL.value}:
        return True
    risk_context = build_risk_context(status=status, instance_state=instance_state)
    rules_result = evaluate_risk_rules(status=status, instance_state=instance_state, risk_config=risk_config, risk_context=risk_context)
    return rules_result.allowed
