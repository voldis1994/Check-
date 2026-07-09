from __future__ import annotations

import inspect


def test_risk_rules_do_not_import_decision_layer() -> None:
    import engine.risk.rules as risk_rules_module

    source = inspect.getsource(risk_rules_module)
    assert "engine.decision" not in source
    assert "engine.reason" in source
