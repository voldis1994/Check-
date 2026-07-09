from __future__ import annotations

import pytest

from engine.decision.reason import build_reason
from engine.protocol.constants import ALL_REASON_CODES
from engine.protocol.errors import ValidationError


def test_every_reason_code_can_generate_reason_string() -> None:
    for code in sorted(ALL_REASON_CODES):
        reason = build_reason(code, "detail")
        assert reason.startswith(f"{code}: ")


def test_reason_contains_code_and_detail() -> None:
    reason = build_reason("RISK_MAX_DRAWDOWN", "drawdown too high", equity=9500.0)
    assert "RISK_MAX_DRAWDOWN" in reason
    assert "drawdown too high" in reason
    assert "equity=9500.0" in reason


def test_empty_detail_not_allowed() -> None:
    with pytest.raises(ValidationError, match="detail must be a non-empty string"):
        build_reason("RISK_MAX_POSITIONS", "   ")
