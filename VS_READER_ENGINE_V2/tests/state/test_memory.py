from __future__ import annotations

from datetime import datetime, timezone

from engine.core.instance import Instance
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.state.memory import StateMemory


def _bar(index: int) -> NormalizedMarketBar:
    return NormalizedMarketBar(
        time_utc=datetime(2026, 7, 7, 6, index, tzinfo=timezone.utc),
        open=1.1,
        high=1.2,
        low=1.0,
        close=1.15,
        volume=100.0,
        symbol="EURUSD",
        timeframe="M1",
        digits=5,
        point=0.00001,
        bar_index=index,
    )


def test_state_memory_isolates_instances() -> None:
    memory = StateMemory(lookback_bars=5)
    instance_a = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    instance_b = Instance(account_id="12345", symbol="GBPUSD", magic=100002)

    memory.update_market_history(instance_a, (_bar(0), _bar(1)))
    memory.update_market_history(instance_b, (_bar(2),))

    item_a = memory.get(instance_a)
    item_b = memory.get(instance_b)
    assert item_a is not None
    assert item_b is not None
    assert len(item_a.market_history) == 2
    assert len(item_b.market_history) == 1


def test_state_memory_enforces_lookback_bars_limit() -> None:
    memory = StateMemory(lookback_bars=3)
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)

    memory.update_market_history(instance, (_bar(0), _bar(1), _bar(2), _bar(3)))

    item = memory.get(instance)
    assert item is not None
    assert [bar.bar_index for bar in item.market_history] == [1, 2, 3]


def test_state_memory_release_on_deactivation() -> None:
    memory = StateMemory(lookback_bars=5)
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    memory.update_market_history(instance, (_bar(0),))
    assert memory.get(instance) is not None

    memory.release(instance)

    assert memory.get(instance) is None


def test_state_memory_caches_last_analysis_and_decision() -> None:
    from engine.analysis.context import AnalysisContext
    from engine.decision.engine import DecisionResult
    from engine.decision.buy import BuyCandidate
    from engine.decision.sell import SellCandidate
    from engine.protocol.constants import Decision, Side

    memory = StateMemory(lookback_bars=5)
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    analysis_context = AnalysisContext(
        session="LONDON",
        regime="trending",
        news_active=False,
        context_quality=0.9,
        trade_environment="FAVORABLE",
        spread_filter_passed=True,
    )
    buy_candidate = BuyCandidate(
        valid=True,
        invalid_reason=None,
        entry_price=1.1,
        stop_loss=1.09,
        take_profit=1.12,
        component_scores={},
        buy_score=1.0,
    )
    sell_candidate = SellCandidate(
        valid=False,
        invalid_reason="invalid",
        entry_price=0.0,
        stop_loss=0.0,
        take_profit=0.0,
        component_scores={},
        sell_score=0.0,
    )
    decision_result = DecisionResult(
        decision_id="decision-test-1",
        decision=Decision.BUY.value,
        reason="BUY: test",
        preferred_side=Side.BUY.value,
        buy_candidate=buy_candidate,
        sell_candidate=sell_candidate,
        buy_score=1.0,
        sell_score=0.0,
        analysis_context=analysis_context,
    )

    memory.update_analysis_decision(
        instance,
        analysis_context=analysis_context,
        decision_result=decision_result,
    )

    item = memory.get(instance)
    assert item is not None
    assert item.last_analysis_context is analysis_context
    assert item.last_decision_result is decision_result
