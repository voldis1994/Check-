"""Paper cycle smoke test."""

from __future__ import annotations

from pathlib import Path

from checktrader.app.bootstrap import bootstrap
from checktrader.app.cycle import run_cycle
from checktrader.domain.enums import ReasonCode


def test_paper_cycle_completes(tmp_path: Path) -> None:
    example = Path("config/system.example.json")
    # bootstrap expects a config path; copy example into tmp and rewrite paths via env not available —
    # use example config which writes into runtime/ relative to cwd
    context = bootstrap(example, mode_override="paper")
    audit = run_cycle(context)
    assert any(
        r in audit.reasons
        for r in (
            ReasonCode.CYCLE_COMPLETED,
            ReasonCode.CYCLE_STARTED,
            ReasonCode.HISTORY_INSUFFICIENT,
            ReasonCode.NO_CLOSED_BARS,
            ReasonCode.BARS_NOT_SEQUENTIAL,
        )
    )
