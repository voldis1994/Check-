"""AUTO account allow-list trusts MT4 status account_number."""

from __future__ import annotations

from pathlib import Path

from checktrader.application.account_resolve import account_is_allowed, is_auto_account_list
from checktrader.application.cycle import run_cycle
from checktrader.config.models import SystemConfig
from checktrader.observability.reason_codes import ReasonCode
from checktrader.state.store import InstanceRuntimeState
from tests.fixtures.candles import candle_dicts, sequential_m1
from tests.fixtures.helpers import (
    config_for_tmp,
    make_market_snapshot,
    make_status_snapshot,
    prepare_bridge,
)

NOW = "2026-03-01T12:00:00Z"


def test_empty_list_is_auto() -> None:
    assert is_auto_account_list([])
    assert is_auto_account_list(["AUTO"])
    assert not is_auto_account_list(["12345"])


def test_auto_allows_any_mt4_account() -> None:
    cfg = SystemConfig(account={"allowed_account_numbers": []})
    assert account_is_allowed(cfg, "111")
    assert account_is_allowed(cfg, "222")


def test_pinned_rejects_other_account(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path, account={"allowed_account_numbers": ["999"]})
    market = make_market_snapshot(bars_m1=candle_dicts(sequential_m1(n=30)), generated_at_utc=NOW)
    status = make_status_snapshot(generated_at_utc=NOW, account_number="888")
    state = InstanceRuntimeState()
    result = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert result.reason is ReasonCode.ACCOUNT_NOT_ALLOWED


def test_empty_allow_list_accepts_status_account(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path, account={"allowed_account_numbers": []})
    market = make_market_snapshot(bars_m1=candle_dicts(sequential_m1(n=30)), generated_at_utc=NOW)
    status = make_status_snapshot(generated_at_utc=NOW, account_number="555001")
    state = InstanceRuntimeState()
    result = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert result.reason is not ReasonCode.ACCOUNT_NOT_ALLOWED
