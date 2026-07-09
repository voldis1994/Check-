from __future__ import annotations
from pathlib import Path
import pytest
from engine.core.cycle import run_instance_cycle
from engine.core.performance import read_memory_rss_mb
from tests.performance.test_cycle_duration import CYCLE_MAX_DURATION_MS, _instance, _startup_runtime
MAX_MEMORY_GROWTH_MB = 64.0
MEMORY_SAMPLE_CYCLES = (1, 50, 100, 500, 1000)

def _cycle_timestamp_utc(cycle_index: int) -> str:
    total_minutes = 2 + cycle_index
    hour = 6 + total_minutes // 60
    minute = total_minutes % 60
    return f'2026-07-07T{hour:02d}:{minute:02d}:00.000Z'

def test_memory_rss_stabilizes_over_1000_cycles(tmp_path: Path) -> None:
    runtime, simulator, instances = _startup_runtime(tmp_path)
    instance = instances[0]
    samples: dict[int, float] = {}
    for index in range(1, MEMORY_SAMPLE_CYCLES[-1] + 1):
        timestamp_utc = _cycle_timestamp_utc(index)
        simulator.export_tick(instance, timestamp_utc=timestamp_utc)
        result = run_instance_cycle(runtime, instance, use_global_universe=False, timestamp_utc=timestamp_utc)
        assert result.completed
        if index in MEMORY_SAMPLE_CYCLES:
            sample = read_memory_rss_mb()
            if sample is None:
                pytest.skip('memory measurement unavailable on this platform')
            samples[index] = sample
    warmup_growth = samples[50] - samples[1]
    late_growth = samples[MEMORY_SAMPLE_CYCLES[-1]] - samples[MEMORY_SAMPLE_CYCLES[-2]]
    total_growth = samples[MEMORY_SAMPLE_CYCLES[-1]] - samples[1]
    assert total_growth < MAX_MEMORY_GROWTH_MB
    assert late_growth <= warmup_growth + MAX_MEMORY_GROWTH_MB / 4
    assert samples[MEMORY_SAMPLE_CYCLES[-1]] > 0

def test_memory_sampling_uses_cycle_max_duration_config(tmp_path: Path) -> None:
    runtime, _simulator, instances = _startup_runtime(tmp_path)
    assert runtime.config.runtime.cycle_max_duration_ms == CYCLE_MAX_DURATION_MS
    assert instances[0] == _instance()
