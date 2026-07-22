"""Setup model field and repository tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from checktrader.domain.enums import ReasonCode, SetupState, Side, StrategyType
from checktrader.domain.models import Setup
from checktrader.setups.repository import SetupRepository


def _make_setup(
    *,
    symbol: str = "EURUSD",
    strategy: StrategyType = StrategyType.TREND_CONTINUATION,
    side: Side = Side.BUY,
    state: SetupState = SetupState.ARMED,
    trigger: float = 1.1000,
    stop: float = 1.0980,
    tp: float = 1.1040,
) -> Setup:
    bar_time = datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC)
    return Setup.create(
        symbol=symbol,
        strategy=strategy,
        side=side,
        state=state,
        created_at_bar=bar_time,
        trigger_level=trigger,
        stop_loss=stop,
        take_profit=tp,
        expires_at_bar=bar_time + timedelta(hours=1),
        reason=ReasonCode.SETUP_ARMED,
        metadata={"ema20": 1.1001, "atr": 0.0010},
    )


# ── Setup dataclass fields ─────────────────────────────────────────────────────


def test_setup_has_setup_id() -> None:
    s = _make_setup()
    assert hasattr(s, "setup_id")
    assert isinstance(s.setup_id, str)
    assert len(s.setup_id) > 0


def test_setup_has_symbol() -> None:
    s = _make_setup(symbol="GBPUSD")
    assert s.symbol == "GBPUSD"


def test_setup_has_strategy() -> None:
    s = _make_setup(strategy=StrategyType.BREAKOUT)
    assert s.strategy == StrategyType.BREAKOUT


def test_setup_has_side() -> None:
    s = _make_setup(side=Side.SELL)
    assert s.side == Side.SELL


def test_setup_has_state() -> None:
    s = _make_setup(state=SetupState.ARMED)
    assert s.state == SetupState.ARMED


def test_setup_has_trigger_price() -> None:
    """Setup trigger level is accessible as trigger_level (new name)."""
    s = _make_setup(trigger=1.2345)
    # Accept either trigger_level (new) or trigger_price (old)
    if hasattr(s, "trigger_level"):
        assert s.trigger_level == pytest.approx(1.2345)
    else:
        assert s.trigger_price == pytest.approx(1.2345)  # type: ignore[attr-defined]


def test_setup_has_stop_loss() -> None:
    s = _make_setup(stop=1.0900)
    assert s.stop_loss == pytest.approx(1.0900)


def test_setup_has_take_profit() -> None:
    s = _make_setup(tp=1.1200)
    assert s.take_profit == pytest.approx(1.1200)


def test_setup_has_created_at_bar() -> None:
    s = _make_setup()
    assert hasattr(s, "created_at_bar")
    assert isinstance(s.created_at_bar, datetime)


def test_setup_has_expires_at_bar() -> None:
    s = _make_setup()
    assert hasattr(s, "expires_at_bar")


def test_setup_has_reason() -> None:
    s = _make_setup()
    assert hasattr(s, "reason")
    assert isinstance(s.reason, ReasonCode)


def test_setup_has_metadata() -> None:
    s = _make_setup()
    assert hasattr(s, "metadata")
    assert isinstance(s.metadata, dict)
    assert "ema20" in s.metadata
    assert "atr" in s.metadata


def test_setup_id_is_unique() -> None:
    s1 = _make_setup()
    s2 = _make_setup()
    assert s1.setup_id != s2.setup_id


def test_setup_id_format_contains_strategy_and_side() -> None:
    s = _make_setup(strategy=StrategyType.TREND_CONTINUATION, side=Side.BUY)
    assert "TREND_CONTINUATION" in s.setup_id.upper() or "trend" in s.setup_id.lower()
    assert "BUY" in s.setup_id.upper() or "buy" in s.setup_id.lower()


# ── Setup serialization ────────────────────────────────────────────────────────


def test_setup_to_dict() -> None:
    s = _make_setup()
    d = s.to_dict()
    assert isinstance(d, dict)
    assert "setup_id" in d
    assert "symbol" in d
    assert "strategy" in d
    assert "state" in d
    # Accept either trigger_level or trigger_price key in dict
    has_trigger = "trigger_level" in d or "trigger_price" in d
    assert has_trigger
    assert "stop_loss" in d
    assert "take_profit" in d
    assert "metadata" in d


# ── SetupRepository ────────────────────────────────────────────────────────────


def test_repository_upsert_and_get() -> None:
    repo = SetupRepository()
    s = _make_setup()
    repo.upsert(s)
    fetched = repo.get(s.setup_id)
    assert fetched is not None
    assert fetched.setup_id == s.setup_id


def test_repository_active_filters_terminal() -> None:
    from checktrader.setups.state_machine import transition

    repo = SetupRepository()
    s1 = _make_setup(side=Side.BUY)
    s2 = _make_setup(side=Side.SELL)
    repo.upsert(s1)
    repo.upsert(s2)
    transition(s2, SetupState.CANCELLED)
    repo.upsert(s2)

    active = repo.active()
    assert len(active) == 1
    assert active[0].setup_id == s1.setup_id


def test_repository_active_filters_by_strategy() -> None:
    repo = SetupRepository()
    s1 = _make_setup(strategy=StrategyType.TREND_CONTINUATION)
    s2 = _make_setup(strategy=StrategyType.BREAKOUT)
    repo.upsert(s1)
    repo.upsert(s2)

    trend_active = repo.active(strategy=StrategyType.TREND_CONTINUATION)
    assert all(s.strategy == StrategyType.TREND_CONTINUATION for s in trend_active)


def test_repository_active_filters_by_symbol() -> None:
    repo = SetupRepository()
    s1 = _make_setup(symbol="EURUSD")
    s2 = _make_setup(symbol="GBPUSD")
    repo.upsert(s1)
    repo.upsert(s2)

    eur_setups = repo.active(symbol="EURUSD")
    assert all(s.symbol == "EURUSD" for s in eur_setups)
    assert len(eur_setups) == 1


def test_repository_roundtrip_serialization() -> None:
    repo = SetupRepository()
    s = _make_setup()
    repo.upsert(s)

    serialized = repo.to_list()
    repo2 = SetupRepository.from_list(serialized)
    fetched = repo2.get(s.setup_id)
    assert fetched is not None
    assert fetched.symbol == s.symbol
    assert fetched.state == s.state
    trigger_orig = getattr(s, "trigger_level", getattr(s, "trigger_price", None))
    trigger_fetched = getattr(fetched, "trigger_level", getattr(fetched, "trigger_price", None))
    assert trigger_fetched == pytest.approx(trigger_orig)
