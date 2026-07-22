"""Multi-account live orchestration."""

from __future__ import annotations

from pathlib import Path

from checktrader.application.cycle import run_cycle
from checktrader.state.store import InstanceRuntimeState, account_state_path, load_instance_state, save_instance_state
from tests.fixtures.candles import candle_dicts, sequential_m1
from tests.fixtures.helpers import config_for_tmp, make_market_snapshot, make_status_snapshot, prepare_bridge

NOW = "2026-03-01T12:00:00Z"


def test_two_accounts_keep_separate_state(tmp_path: Path) -> None:
    config = config_for_tmp(tmp_path, account={"allowed_account_numbers": []})
    bridge_a = prepare_bridge(tmp_path / "a")
    bridge_b = prepare_bridge(tmp_path / "b")

    market = make_market_snapshot(bars_m1=candle_dicts(sequential_m1(n=30)), generated_at_utc=NOW)
    status_a = make_status_snapshot(generated_at_utc=NOW, account_number="231054")
    status_b = make_status_snapshot(generated_at_utc=NOW, account_number="231443")

    path_a = account_state_path(tmp_path, config.paths.state, "231054")
    path_b = account_state_path(tmp_path, config.paths.state, "231443")
    path_a.parent.mkdir(parents=True, exist_ok=True)
    state_a = InstanceRuntimeState()
    state_b = InstanceRuntimeState()

    r1 = run_cycle(
        config=config,
        state=state_a,
        market=market,
        status=status_a,
        bridge_root=bridge_a,
        now_utc=NOW,
        state_path=path_a,
    )
    r2 = run_cycle(
        config=config,
        state=state_b,
        market=market,
        status=status_b,
        bridge_root=bridge_b,
        now_utc=NOW,
        state_path=path_b,
    )
    assert r1.reason.value != "ACCOUNT_NOT_ALLOWED"
    assert r2.reason.value != "ACCOUNT_NOT_ALLOWED"
    save_instance_state(path_a, state_a, now_utc=NOW)
    save_instance_state(path_b, state_b, now_utc=NOW)

    assert path_a.exists() and path_b.exists()
    assert path_a != path_b
    assert load_instance_state(path_a).sequence == state_a.sequence
    assert load_instance_state(path_b).sequence == state_b.sequence
