from __future__ import annotations

import json
import pytest

from engine.ai_decision_layer import AIDecision


@pytest.fixture(autouse=True)
def _mock_openai_for_tests(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """
    Deterministic OpenAI mock for most tests. Mark a test with ``no_ai_mock`` to
    exercise advisory fallback / required blocking without this fixture.
    """
    if request.node.get_closest_marker("no_ai_mock"):
        return

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    import engine.ai_decision_layer as mdl

    def _fake_call_openai(*_args, **_kwargs) -> str:
        # The prompt contains: "System signal: {DECISION}"
        prompt = _kwargs.get("prompt") or _args[-1]  # best-effort
        prompt_text = str(prompt)
        system_signal = "UNKNOWN"
        if "System signal:" in prompt_text:
            system_signal = prompt_text.split("System signal:", 1)[1].strip().splitlines()[0].strip()

        if system_signal == "BUY":
            ai = AIDecision(
                bias="BULLISH",
                confidence=0.9,
                allow_buy=True,
                allow_sell=False,
                allow_close=True,
                reason="mock allows BUY",
            )
        elif system_signal == "SELL":
            ai = AIDecision(
                bias="BEARISH",
                confidence=0.9,
                allow_buy=False,
                allow_sell=True,
                allow_close=True,
                reason="mock allows SELL",
            )
        else:
            ai = AIDecision(
                bias="NEUTRAL",
                confidence=0.5,
                allow_buy=True,
                allow_sell=True,
                allow_close=True,
                reason="mock neutral",
            )
        return json.dumps(
            {
                "bias": ai.bias,
                "confidence": ai.confidence,
                "allow_buy": ai.allow_buy,
                "allow_sell": ai.allow_sell,
                "allow_close": ai.allow_close,
                "reason": ai.reason,
            }
        )

    monkeypatch.setattr(mdl, "_call_openai", _fake_call_openai)

