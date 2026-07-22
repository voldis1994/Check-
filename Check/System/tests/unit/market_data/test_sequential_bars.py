from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from checktrader.app.live_loop import select_bridge
from checktrader.domain.enums import ReasonCode
from checktrader.domain.models import Candle
from checktrader.market_data.validation import sequential_bars


def _bar(ts: datetime) -> Candle:
    return Candle(ts, 1.0, 1.1, 0.9, 1.05, 1.0, "M15", True)


def test_sequential_bars_allows_session_gap_multiples() -> None:
    t0 = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
    bars = [
        _bar(t0),
        _bar(t0 + timedelta(minutes=15)),
        _bar(t0 + timedelta(minutes=60)),  # 3x gap after session hole
    ]
    ok, reason = sequential_bars(bars, "M15")
    assert ok is True
    assert reason == ReasonCode.DATA_VALID


def test_sequential_bars_rejects_misaligned_gap() -> None:
    t0 = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
    bars = [
        _bar(t0),
        _bar(t0 + timedelta(minutes=10)),  # not a multiple of 15
    ]
    ok, reason = sequential_bars(bars, "M15")
    assert ok is False
    assert reason == ReasonCode.BARS_NOT_SEQUENTIAL


def test_select_bridge_prefers_freshest(tmp_path: Path) -> None:
    import os
    import time

    a = tmp_path / "a" / "market"
    b = tmp_path / "b" / "market"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    (a / "latest.json").write_text("{}", encoding="utf-8")
    (b / "latest.json").write_text("{}", encoding="utf-8")
    older = (tmp_path / "a").resolve()
    newer = (tmp_path / "b").resolve()
    now = time.time()
    os.utime(a / "latest.json", (now - 120, now - 120))
    os.utime(b / "latest.json", (now, now))
    chosen = select_bridge([older, newer])
    assert chosen == newer
    sticky = select_bridge([older, newer], sticky=newer)
    assert sticky == newer
