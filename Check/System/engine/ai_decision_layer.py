from __future__ import annotations
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from engine.protocol.constants import Decision, RiskResult
from engine.protocol.models import AIConfig
from engine.risk.engine import RiskEngineResult
MODULE_NAME = 'ai.decision_layer'

@dataclass(frozen=True)
class AIDecision:
    bias: str
    confidence: float
    allow_buy: bool
    allow_sell: bool
    allow_close: bool
    reason: str

@dataclass(frozen=True)
class AIQueryResult:
    decision: AIDecision | None
    error_type: str | None = None

    @property
    def available(self) -> bool:
        return self.decision is not None

@dataclass(frozen=True)
class AIDecisionMeta:
    ai_mode: str
    ai_available: bool
    ai_error_type: str | None
    ai_fallback_used: bool
    ai_reason: str | None
    system_decision_before_ai: str
    decision_after_ai: str
_BIAS_ALLOWED = {'BULLISH', 'BEARISH', 'NEUTRAL', 'AVOID'}
_ERROR_FALLBACK_REASONS = {'timeout': 'ai_timeout_system_fallback', 'api_error': 'ai_error_system_fallback', 'invalid_json': 'ai_invalid_json_system_fallback', 'missing_key': 'ai_error_system_fallback'}

def _json_extract(text: str) -> str | None:
    text = text.strip()
    if text.startswith('{') and text.endswith('}'):
        return text
    match = re.search('\\{.*\\}', text, flags=re.DOTALL)
    if not match:
        return None
    return match.group(0)

def parse_ai_decision_json(text: str) -> AIDecision | None:
    extracted = _json_extract(text)
    if extracted is None:
        return None
    try:
        payload = json.loads(extracted)
    except Exception:
        return None
    try:
        bias = str(payload['bias'])
        confidence = float(payload['confidence'])
        allow_buy = bool(payload['allow_buy'])
        allow_sell = bool(payload['allow_sell'])
        allow_close = bool(payload['allow_close'])
        reason = str(payload['reason'])
    except Exception:
        return None
    if bias not in _BIAS_ALLOWED:
        return None
    if confidence < 0.0 or confidence > 1.0:
        return None
    if not reason:
        return None
    return AIDecision(bias=bias, confidence=confidence, allow_buy=allow_buy, allow_sell=allow_sell, allow_close=allow_close, reason=reason)

def _build_openai_prompt(*, system_signal: str, market_context: dict[str, Any]) -> str:
    context_text = json.dumps(market_context, ensure_ascii=False, default=str)
    return f'You are a strict decision layer for a trading system.\nYou must output ONLY valid JSON with this exact schema:\n{{\n  "bias": "BULLISH|BEARISH|NEUTRAL|AVOID",\n  "confidence": 0.0, \n  "allow_buy": true, \n  "allow_sell": false, \n  "allow_close": true, \n  "reason": "..." \n}}\n\nRules reminder:\n- If you say bias=AVOID, the final decision must be BLOCK.\n- If you set allow_buy/allow_sell to false, the system signal must be blocked.\n- Do NOT output any additional keys.\n- Output MUST be parseable JSON.\n\nSystem signal: {system_signal}\nMarket context: {context_text}\n'

def _call_openai(*, api_key: str, prompt: str, timeout_s: int, retry_max: int, retry_delay_ms: int) -> str:
    url = 'https://api.openai.com/v1/chat/completions'
    data = {'model': 'gpt-4o-mini', 'temperature': 0.0, 'messages': [{'role': 'system', 'content': 'Return strictly valid JSON only.'}, {'role': 'user', 'content': prompt}]}
    payload = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url=url, data=payload, method='POST', headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'})
    last_error: Exception | None = None
    for attempt in range(retry_max + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
            obj = json.loads(raw)
            content = obj['choices'][0]['message']['content']
            return str(content)
        except (socket.timeout, TimeoutError) as exc:
            last_error = exc
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in {429, 500, 502, 503, 504} and attempt < retry_max:
                time.sleep(retry_delay_ms / 1000.0)
                continue
            raise
        except Exception as exc:
            last_error = exc
        if attempt < retry_max:
            time.sleep(retry_delay_ms / 1000.0)
    if last_error is not None:
        raise last_error
    raise RuntimeError('OpenAI request failed without error detail')

def _timeout_seconds(ai_config: AIConfig | None) -> int:
    if ai_config is None:
        return 10
    return max(1, int(ai_config.timeout_ms / 1000))

def get_ai_decision(*, system_signal: str, market_context: dict[str, Any], ai_config: AIConfig | None=None, skip_reason: str | None=None) -> AIQueryResult:
    if ai_config is not None and ai_config.mode == 'off':
        return AIQueryResult(decision=None, error_type='disabled')
    if skip_reason is not None:
        return AIQueryResult(decision=None, error_type=skip_reason)
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return AIQueryResult(decision=None, error_type='missing_key')
    prompt = _build_openai_prompt(system_signal=system_signal, market_context=market_context)
    timeout_s = _timeout_seconds(ai_config)
    retry_max = 0 if ai_config is None else ai_config.retry_max
    retry_delay_ms = 0 if ai_config is None else ai_config.retry_delay_ms
    try:
        content = _call_openai(api_key=api_key, prompt=prompt, timeout_s=timeout_s, retry_max=retry_max, retry_delay_ms=retry_delay_ms)
    except (socket.timeout, TimeoutError):
        return AIQueryResult(decision=None, error_type='timeout')
    except Exception:
        return AIQueryResult(decision=None, error_type='api_error')
    parsed = parse_ai_decision_json(content)
    if parsed is None:
        return AIQueryResult(decision=None, error_type='invalid_json')
    return AIQueryResult(decision=parsed, error_type=None)

def resolve_ai_allow_close(ai_query: AIQueryResult) -> bool:
    if ai_query.decision is None:
        return True
    return ai_query.decision.allow_close

def _is_fail_closed(config: AIConfig) -> bool:
    return config.mode == 'required' or config.fail_closed

def _fallback_reason(error_type: str | None) -> str:
    if error_type is None:
        return 'ai_error_system_fallback'
    return _ERROR_FALLBACK_REASONS.get(error_type, 'ai_error_system_fallback')

def apply_ai_advisory_decision(*, system_decision: str, system_reason: str, ai_result: AIDecision | None, ai_error: str | None, config: AIConfig) -> tuple[str, str, bool, str | None]:
    if ai_result is None:
        if ai_error in {'skipped_risk_precheck', 'disabled'}:
            return (system_decision, system_reason, False, None)
        if _is_fail_closed(config):
            return (Decision.BLOCK.value, 'ai_required_missing_block', False, None)
        fallback_used = True
        fallback_code = _fallback_reason(ai_error)
        if system_decision in {Decision.BUY.value, Decision.SELL.value}:
            return (system_decision, f'{fallback_code}: {system_reason}', fallback_used, None)
        if system_reason:
            return (system_decision, f'{fallback_code}: {system_reason}', fallback_used, None)
        return (system_decision, fallback_code, fallback_used, None)
    if ai_result.bias == 'AVOID':
        if system_decision in {Decision.WAIT.value, Decision.BLOCK.value}:
            return (system_decision, system_reason, False, ai_result.reason)
        return (Decision.BLOCK.value, f'ai_veto_avoid: {ai_result.reason}', False, ai_result.reason)
    if system_decision == Decision.BUY.value and (not ai_result.allow_buy):
        reject = config.reject_action
        return (reject, f'ai_veto_buy_rejected: {ai_result.reason}', False, ai_result.reason)
    if system_decision == Decision.SELL.value and (not ai_result.allow_sell):
        reject = config.reject_action
        return (reject, f'ai_veto_sell_rejected: {ai_result.reason}', False, ai_result.reason)
    if system_decision in {Decision.WAIT.value, Decision.BLOCK.value}:
        return (system_decision, system_reason, False, ai_result.reason)
    return (system_decision, f'ai_allowed: {ai_result.reason}', False, ai_result.reason)

def decide_ai_decision(*, system_signal: str, system_reason: str, ai_query: AIQueryResult, ai_config: AIConfig) -> tuple[str, str, AIDecisionMeta]:
    ai_decision, reason, fallback_used, ai_reason = apply_ai_advisory_decision(system_decision=system_signal, system_reason=system_reason, ai_result=ai_query.decision, ai_error=ai_query.error_type, config=ai_config)
    meta = AIDecisionMeta(ai_mode=ai_config.mode, ai_available=ai_query.available, ai_error_type=ai_query.error_type, ai_fallback_used=fallback_used, ai_reason=ai_reason, system_decision_before_ai=system_signal, decision_after_ai=ai_decision)
    return (ai_decision, reason, meta)

def apply_risk_block_to_decision_result(*, decision_result: Any, risk_engine_result: RiskEngineResult) -> Any:
    if decision_result.decision not in {Decision.BUY.value, Decision.SELL.value}:
        return decision_result
    if risk_engine_result.result != RiskResult.BLOCK.value:
        return decision_result
    reason = risk_engine_result.reason.strip() or 'RISK_FAIL: risk rules blocked'
    if not reason.startswith('RISK_FAIL'):
        reason = f'RISK_FAIL: {reason}'
    return decision_result.__class__(decision_id=decision_result.decision_id, decision=Decision.BLOCK.value, reason=reason, preferred_side=decision_result.preferred_side, buy_candidate=decision_result.buy_candidate, sell_candidate=decision_result.sell_candidate, buy_score=decision_result.buy_score, sell_score=decision_result.sell_score, analysis_context=decision_result.analysis_context)

def decide_final_decision(*, system_signal: str, system_reason: str, ai_query: AIQueryResult, risk_engine_result: RiskEngineResult, ai_config: AIConfig) -> tuple[str, str, AIDecisionMeta]:
    ai_decision, reason, meta = decide_ai_decision(system_signal=system_signal, system_reason=system_reason, ai_query=ai_query, ai_config=ai_config)
    if ai_decision in {Decision.BUY.value, Decision.SELL.value} and risk_engine_result.result != RiskResult.ALLOW.value:
        return (Decision.BLOCK.value, 'RISK_FAIL: risk rules blocked', meta)
    return (ai_decision, reason, meta)

def apply_ai_to_decision_result(*, decision_result: Any, ai_query: AIQueryResult, ai_config: AIConfig) -> tuple[Any, AIDecisionMeta]:
    final_decision, final_reason, meta = decide_ai_decision(system_signal=decision_result.decision, system_reason=decision_result.reason, ai_query=ai_query, ai_config=ai_config)
    if final_decision == decision_result.decision and decision_result.decision in {Decision.WAIT.value, Decision.BLOCK.value} and (ai_query.decision is not None) and (ai_query.decision.bias != 'AVOID') and (not meta.ai_fallback_used):
        return (decision_result, meta)
    if final_decision == decision_result.decision and final_reason == decision_result.reason:
        return (decision_result, meta)
    updated = decision_result.__class__(decision_id=decision_result.decision_id, decision=final_decision, reason=final_reason, preferred_side=decision_result.preferred_side, buy_candidate=decision_result.buy_candidate, sell_candidate=decision_result.sell_candidate, buy_score=decision_result.buy_score, sell_score=decision_result.sell_score, analysis_context=decision_result.analysis_context)
    return (updated, meta)
