from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Mapping
from engine.core.instance import Instance
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.state.instance_state import InstanceState
from engine.state.spread_state import SpreadState
if TYPE_CHECKING:
    from engine.analysis.context import AnalysisContext
    from engine.decision.engine import DecisionResult

@dataclass
class InstanceMemory:
    instance: Instance
    instance_state: InstanceState
    spread_state: SpreadState
    market_history: list[NormalizedMarketBar] = field(default_factory=list)
    last_analysis_context: AnalysisContext | None = None
    last_decision_result: DecisionResult | None = None

class StateMemory:

    def __init__(self, *, lookback_bars: int) -> None:
        if lookback_bars <= 0:
            raise ValueError('lookback_bars must be positive')
        self._lookback_bars = lookback_bars
        self._instances: dict[tuple[str, str, int], InstanceMemory] = {}

    def get_or_create(self, instance: Instance) -> InstanceMemory:
        key = instance.instance_key
        memory = self._instances.get(key)
        if memory is None:
            memory = InstanceMemory(instance=instance, instance_state=InstanceState(instance=instance), spread_state=SpreadState(instance=instance))
            self._instances[key] = memory
        return memory

    def get(self, instance: Instance) -> InstanceMemory | None:
        return self._instances.get(instance.instance_key)

    def update_market_history(self, instance: Instance, bars: tuple[NormalizedMarketBar, ...]) -> InstanceMemory:
        memory = self.get_or_create(instance)
        memory.market_history.extend(bars)
        if len(memory.market_history) > self._lookback_bars:
            memory.market_history = memory.market_history[-self._lookback_bars:]
        return memory

    def update_analysis_decision(self, instance: Instance, *, analysis_context: AnalysisContext, decision_result: DecisionResult) -> InstanceMemory:
        memory = self.get_or_create(instance)
        memory.last_analysis_context = analysis_context
        memory.last_decision_result = decision_result
        return memory

    def release(self, instance: Instance) -> None:
        self._instances.pop(instance.instance_key, None)

    def items(self) -> Mapping[tuple[str, str, int], InstanceMemory]:
        return dict(self._instances)
