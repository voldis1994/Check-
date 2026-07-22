"""MT4 chart symbol drives trading when config is AUTO."""

from __future__ import annotations

from pathlib import Path

from checktrader.application.cycle import run_cycle
from checktrader.application.symbol_resolve import is_auto_symbol, resolve_trading_symbol
from checktrader.config.models import SystemConfig
from checktrader.market_data.loader import parse_market_snapshot
from checktrader.observability.reason_codes import ReasonCode
from checktrader.state.store import InstanceRuntimeState
from tests.fixtures.candles import candle_dicts, sequential_m1
from tests.fixtures.helpers import (
    config_for_tmp,
    eurusd_market_payload,
    make_status_snapshot,
    prepare_bridge,
)

NOW = "2026-03-01T12:00:00Z"


def test_auto_tokens() -> None:
    assert is_auto_symbol("AUTO")
    assert is_auto_symbol("*")
    assert is_auto_symbol("")
    assert not is_auto_symbol("NATURALGAS")


def test_resolve_auto_uses_market_symbol() -> None:
    cfg = SystemConfig(instrument={"symbol": "AUTO"}, account={"allowed_account_numbers": ["999"]})
    payload = eurusd_market_payload(bars_m1=candle_dicts(sequential_m1(n=5)))
    payload["symbol"] = "NATURALGAS"
    market = parse_market_snapshot(payload)
    symbol, mode = resolve_trading_symbol(cfg, market)
    assert mode == "auto"
    assert symbol == "NATURALGAS"


def test_pinned_mismatch(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path, instrument={"symbol": "EURUSD"})
    payload = eurusd_market_payload(bars_m1=candle_dicts(sequential_m1(n=30)), generated_at_utc=NOW)
    payload["symbol"] = "NATURALGAS"
    market = parse_market_snapshot(payload)
    status = make_status_snapshot(generated_at_utc=NOW)
    state = InstanceRuntimeState()
    result = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert result.reason is ReasonCode.SYMBOL_MISMATCH


def test_auto_accepts_naturalgas_chart(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path, instrument={"symbol": "AUTO"})
    payload = eurusd_market_payload(bars_m1=candle_dicts(sequential_m1(n=30)), generated_at_utc=NOW)
    payload["symbol"] = "NATURALGAS"
    market = parse_market_snapshot(payload)
    status = make_status_snapshot(generated_at_utc=NOW)
    state = InstanceRuntimeState()
    result = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert result.reason is not ReasonCode.SYMBOL_MISMATCH
    symbol, mode = resolve_trading_symbol(config, market)
    assert symbol == "NATURALGAS" and mode == "auto"
