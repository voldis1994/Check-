"""Trend pullback strategy tests."""

from __future__ import annotations

from checktrader.config.models import StrategyConfig
from checktrader.domain.enums import SetupState, StrategyResult
from checktrader.observability.reason_codes import ReasonCode
from checktrader.strategy.engine import run_strategy
from checktrader.strategy.trend_pullback import is_setup_expired
from tests.fixtures.candles import synthesize_buy_setup_m1, synthesize_sell_setup_m1, synthesize_unclear_m1
from tests.fixtures.helpers import EURUSD_SPECS


def _cfg(**kwargs: object) -> StrategyConfig:
    base = dict(
        minimum_structure_bars=30,
        hma_period=21,
        atr_period=14,
        pullback_min_atr=0.0,
        pullback_max_atr=2.0,
        trigger_buffer_atr=0.05,
        maximum_stop_atr=5.0,
        setup_expiry_bars=200,
        use_closed_bars_only=True,
    )
    base.update(kwargs)
    return StrategyConfig(**base)  # type: ignore[arg-type]


def test_buy_m15_bias_entry() -> None:
    bars = synthesize_buy_setup_m1(trigger=True)
    d = run_strategy(symbol="EURUSD", specs=EURUSD_SPECS, bars_m1=bars, config=_cfg(), now_utc="2026-03-01T12:00:00Z")
    assert d.result is StrategyResult.ENTRY_BUY
    assert d.setup is not None
    assert d.setup.state is SetupState.TRIGGERED


def test_sell_m15_bias_entry() -> None:
    bars = synthesize_sell_setup_m1(trigger=True)
    d = run_strategy(symbol="EURUSD", specs=EURUSD_SPECS, bars_m1=bars, config=_cfg(), now_utc="2026-03-01T12:00:00Z")
    assert d.result is StrategyResult.ENTRY_SELL


def test_unclear_m15_no_signal() -> None:
    bars = synthesize_unclear_m1()
    d = run_strategy(symbol="EURUSD", specs=EURUSD_SPECS, bars_m1=bars, config=_cfg(), now_utc="2026-03-01T12:00:00Z")
    assert d.result is StrategyResult.NO_SIGNAL
    assert d.reason is ReasonCode.NO_SIGNAL
    assert (d.evidence or {}).get("why") == "unclear_m15"


def test_pullback_arms_without_trigger() -> None:
    bars = synthesize_buy_setup_m1(trigger=False)
    d = run_strategy(symbol="EURUSD", specs=EURUSD_SPECS, bars_m1=bars, config=_cfg(), now_utc="2026-03-01T12:00:00Z")
    assert d.result is StrategyResult.NO_SIGNAL
    assert d.reason is ReasonCode.SETUP_ARMED
    assert d.setup is not None
    assert d.setup.state is SetupState.ARMED


def test_setup_expiry() -> None:
    bars = synthesize_buy_setup_m1(trigger=False)
    d = run_strategy(
        symbol="EURUSD",
        specs=EURUSD_SPECS,
        bars_m1=bars,
        config=_cfg(setup_expiry_bars=3),
        now_utc="2026-03-01T12:00:00Z",
    )
    assert d.reason is ReasonCode.SETUP_EXPIRED
    assert d.setup is not None
    assert d.setup.state is SetupState.EXPIRED
    assert is_setup_expired(origin_utc=d.setup.setup_origin_timestamp, bars_m1=bars, setup_expiry_bars=3)


def test_fingerprint_stable_across_extra_m1() -> None:
    base = synthesize_buy_setup_m1(trigger=False)
    d1 = run_strategy(symbol="EURUSD", specs=EURUSD_SPECS, bars_m1=base, config=_cfg(), now_utc="2026-03-01T12:00:00Z")
    # Append M1 that does not complete a new M5/M15 bucket → same HTF structure
    from datetime import datetime, timedelta

    from tests.fixtures.candles import make_m1_candle

    last = base[-1]
    t = (datetime.fromisoformat(last.open_time_utc.replace("Z", "+00:00")) + timedelta(minutes=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    extended = base + [
        make_m1_candle(
            open_time_utc=t, open_=last.close, high=last.close + 0.00002, low=last.close - 0.00002, close=last.close
        )
    ]
    d2 = run_strategy(
        symbol="EURUSD", specs=EURUSD_SPECS, bars_m1=extended, config=_cfg(), now_utc="2026-03-01T12:01:00Z"
    )
    assert d1.setup is not None and d2.setup is not None
    assert d1.setup.fingerprint == d2.setup.fingerprint


def test_new_structure_new_fingerprint() -> None:
    a = synthesize_buy_setup_m1(trigger=False, start_utc="2026-01-01T00:00:00Z")
    b = synthesize_buy_setup_m1(trigger=False, start_utc="2026-02-01T00:00:00Z")
    d1 = run_strategy(symbol="EURUSD", specs=EURUSD_SPECS, bars_m1=a, config=_cfg(), now_utc="2026-03-01T12:00:00Z")
    d2 = run_strategy(symbol="EURUSD", specs=EURUSD_SPECS, bars_m1=b, config=_cfg(), now_utc="2026-03-01T12:00:00Z")
    assert d1.setup is not None and d2.setup is not None
    assert d1.setup.fingerprint != d2.setup.fingerprint
