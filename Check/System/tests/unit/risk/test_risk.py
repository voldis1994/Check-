"""Risk and execution unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from checktrader.bridge.atomic_files import read_json, write_json_atomic
from checktrader.config.loader import load_config
from checktrader.domain.enums import ReasonCode
from checktrader.domain.models import LimitState, SymbolSpecs
from checktrader.execution.idempotency import CommandDedupe
from checktrader.risk.limits import record_trade_open, validate_limits
from checktrader.risk.spread import validate_spread


def test_spread_filter(specs: SymbolSpecs) -> None:
    cfg = load_config()
    reason = validate_spread(bid=1.0, ask=1.0001, atr_value=0.01, specs=specs, config=cfg.spread)
    assert reason in {
        ReasonCode.RISK_ACCEPTED,
        ReasonCode.SPREAD_POINTS_TOO_HIGH,
        ReasonCode.SPREAD_ATR_TOO_HIGH,
        ReasonCode.SPREAD_TOO_HIGH,
    }


def test_daily_trade_limit() -> None:
    cfg = load_config()
    limits = cfg.limits.model_copy(update={"max_daily_trades": 6})
    state = LimitState(trade_date="")
    now = datetime(2026, 3, 1, tzinfo=UTC)
    for _ in range(limits.max_daily_trades):
        assert validate_limits(state, limits, now) is ReasonCode.RISK_ACCEPTED
        record_trade_open(state, now)
    assert validate_limits(state, limits, now) is ReasonCode.RISK_DAILY_TRADES_LIMIT


def test_command_dedupe() -> None:
    store = CommandDedupe(window_seconds=60.0)
    now = datetime(2026, 3, 1, tzinfo=UTC)
    assert store.remember("abc", now) is True
    assert store.remember("abc", now) is False


def test_atomic_write(tmp_path: Path) -> None:
    path = tmp_path / "x.json"
    write_json_atomic(path, {"a": 1})
    data = read_json(path)
    assert data is not None
    assert data["a"] == 1
