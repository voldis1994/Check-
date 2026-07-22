"""Shared pytest fixtures for CHECK SYSTEM v3."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from checktrader.config.loader import load_config
from checktrader.config.models import SystemConfig
from checktrader.domain.models import Candle, SymbolSpecs


@pytest.fixture
def config() -> SystemConfig:
    return load_config()


@pytest.fixture
def specs() -> SymbolSpecs:
    return SymbolSpecs(
        symbol="TEST",
        digits=5,
        point=0.00001,
        tick_size=0.00001,
        pip_size=0.0001,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
        contract_size=100000.0,
        stop_level_points=10.0,
        freeze_level_points=0.0,
    )


def make_m15_series(
    n: int,
    *,
    start: float = 100.0,
    drift: float = 0.05,
    noise: float = 0.02,
    start_time: datetime | None = None,
) -> list[Candle]:
    """Deterministic synthetic M15 closed bars."""
    t0 = start_time or datetime(2026, 1, 1, tzinfo=UTC)
    out: list[Candle] = []
    price = start
    for i in range(n):
        # mild sine-like noise without randomness
        wobble = noise * ((i % 7) - 3) / 3.0
        o = price
        c = price + drift + wobble
        h = max(o, c) + abs(noise)
        low = min(o, c) - abs(noise)
        out.append(
            Candle(
                t0 + timedelta(minutes=15 * i),
                open=o,
                high=h,
                low=low,
                close=c,
                volume=100.0,
                timeframe="M15",
                closed=True,
            )
        )
        price = c
    return out


def make_flat_range_m15(n: int = 80, *, mid: float = 100.0, half_width: float = 1.0) -> list[Candle]:
    t0 = datetime(2026, 2, 1, tzinfo=UTC)
    out: list[Candle] = []
    for i in range(n):
        # oscillate between bounds to create touches
        phase = i % 8
        if phase in {0, 1}:
            o, c = mid - half_width + 0.05, mid - half_width + 0.10
            low = mid - half_width
            h = mid - half_width + 0.3
        elif phase in {4, 5}:
            o, c = mid + half_width - 0.10, mid + half_width - 0.05
            h = mid + half_width
            low = mid + half_width - 0.3
        else:
            o = mid + ((i % 3) - 1) * 0.1
            c = mid + ((i % 5) - 2) * 0.08
            h = max(o, c) + 0.15
            low = min(o, c) - 0.15
        out.append(
            Candle(
                t0 + timedelta(minutes=15 * i),
                open=o,
                high=h,
                low=low,
                close=c,
                volume=50.0,
                timeframe="M15",
                closed=True,
            )
        )
    return out


@pytest.fixture
def runtime_dir(tmp_path: Path) -> Path:
    for rel in (
        "bridge/market",
        "bridge/status",
        "bridge/commands",
        "bridge/acknowledgements",
        "history",
        "state",
        "logs",
    ):
        (tmp_path / rel).mkdir(parents=True)
    return tmp_path
