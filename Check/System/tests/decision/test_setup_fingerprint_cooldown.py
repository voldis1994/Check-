from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from engine.analysis.structure import analyze_structure, derive_setup_type
from engine.core.clock import format_utc_timestamp
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.decision.signal_quality import (
    build_setup_fingerprint,
    build_signal_fingerprint,
    default_signal_quality_dict,
    evaluate_signal_quality,
)
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.constants import (
    REASON_DUPLICATE_SIGNAL,
    REASON_SIGNAL_DELTA_TOO_SMALL,
    Side,
    TradeOutcome,
)
from engine.protocol.models import SignalQualityConfig
from engine.state.instance_state import InstanceState


def _cfg(**overrides: float | int) -> SignalQualityConfig:
    payload = default_signal_quality_dict()
    payload.update(overrides)
    return SignalQualityConfig(**payload)


def _buy_components() -> dict[str, float]:
    return {'momentum': 0.85, 'trend': 0.82, 'structure': 0.80, 'pressure': 0.78, 'behavior': 0.75, 'impact': 0.75, 'context': 0.75}


def _sell_components(*, weak: bool = True) -> dict[str, float]:
    if weak:
        return {'momentum': 0.35, 'trend': 0.32, 'structure': 0.30, 'pressure': 0.28, 'behavior': 0.75, 'impact': 0.75, 'context': 0.75}
    return {'momentum': 0.70, 'trend': 0.68, 'structure': 0.66, 'pressure': 0.64, 'behavior': 0.75, 'impact': 0.75, 'context': 0.75}


def _quality_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        'buy_score': 0.80,
        'sell_score': 0.30,
        'buy_valid': True,
        'sell_valid': True,
        'buy_components': _buy_components(),
        'sell_components': _sell_components(),
        'market_quality_score': 0.75,
        'signal_quality_config': _cfg(),
        'symbol': 'EURUSD',
        'candle_time_utc': '2026-07-07T06:02:00.000Z',
        'structure_level': 1.09950,
        'setup_origin_timestamp': '2026-07-07T06:00:00.000Z',
        'structure_id': 'struct-abc',
        'setup_type': 'continuation_buy',
        'digits': 5,
        'cooldown_bars_remaining': 0,
        'active_fingerprints': {},
    }
    base.update(overrides)
    return base


def _bar(index: int, open_: float, high: float, low: float, close: float) -> NormalizedMarketBar:
    return NormalizedMarketBar(
        time_utc=datetime(2026, 7, 7, 6, index, tzinfo=timezone.utc),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        symbol='EURUSD',
        timeframe='M1',
        digits=5,
        point=1e-05,
        bar_index=index,
    )


def test_same_setup_five_bars_same_fingerprint() -> None:
    # Same impulse: later bars stay inside the initial swing range so structure
    # identity (swing high/low + origin) does not change candle-to-candle.
    base_bars = [
        _bar(0, 1.1000, 1.1010, 1.0990, 1.1002),  # establishes swing high/low
        _bar(1, 1.1002, 1.1008, 1.0992, 1.1005),
        _bar(2, 1.1005, 1.1009, 1.0993, 1.1006),
        _bar(3, 1.1006, 1.1009, 1.0994, 1.1004),
        _bar(4, 1.1004, 1.1008, 1.0995, 1.1007),
        _bar(5, 1.1007, 1.1009, 1.0994, 1.1005),
    ]
    fingerprints: list[str] = []
    origins: list[str] = []
    for end in range(2, 7):
        window = tuple(base_bars[:end])
        structure = analyze_structure(window)
        side = Side.BUY.value
        fp = build_setup_fingerprint(
            symbol='EURUSD',
            direction=side,
            setup_type=derive_setup_type(side=side, structure=structure),
            structure_id=structure.structure_id,
            setup_origin_timestamp=structure.origin_timestamp_for_side(side),
            structure_level=structure.structure_level_for_side(side),
            digits=5,
        )
        fingerprints.append(fp)
        origins.append(structure.origin_timestamp_for_side(side))
        assert structure.setup_origin_timestamp
        assert structure.swing_high == pytest.approx(1.1010)
        assert structure.swing_low == pytest.approx(1.0990)
    assert len(set(fingerprints)) == 1
    assert len(set(origins)) == 1


def test_duplicate_blocks_after_registration_across_candles() -> None:
    structure = analyze_structure(tuple(_bar(i, 1.1, 1.101, 1.099, 1.1005) for i in range(3)))
    fp = build_setup_fingerprint(
        symbol='EURUSD',
        direction=Side.BUY.value,
        setup_type='continuation_buy',
        structure_id=structure.structure_id,
        setup_origin_timestamp=structure.setup_origin_timestamp,
        structure_level=structure.structure_level_for_side(Side.BUY.value),
        digits=5,
    )
    first = evaluate_signal_quality(**_quality_kwargs(structure_id=structure.structure_id, setup_origin_timestamp=structure.setup_origin_timestamp, structure_level=structure.swing_low, candle_time_utc='2026-07-07T06:02:00.000Z'))
    assert first.passed is True
    assert first.fingerprint == fp
    for minute in (3, 4, 5, 6):
        blocked = evaluate_signal_quality(
            **_quality_kwargs(
                structure_id=structure.structure_id,
                setup_origin_timestamp=structure.setup_origin_timestamp,
                structure_level=structure.swing_low,
                candle_time_utc=f'2026-07-07T06:0{minute}:00.000Z',
                active_fingerprints={fp: '10'},
            )
        )
        assert blocked.passed is False
        assert blocked.reason_code == REASON_DUPLICATE_SIGNAL
        assert blocked.fingerprint == fp
        assert blocked.signal_candle_timestamp == f'2026-07-07T06:0{minute}:00.000Z'
        assert blocked.setup_origin_timestamp == structure.setup_origin_timestamp


def test_new_swing_creates_new_fingerprint() -> None:
    first = analyze_structure((_bar(0, 1.1, 1.101, 1.099, 1.1005), _bar(1, 1.1005, 1.1015, 1.0995, 1.1010)))
    # New lower swing low → new structure identity
    second = analyze_structure((_bar(0, 1.1, 1.101, 1.099, 1.1005), _bar(1, 1.1005, 1.1015, 1.0995, 1.1010), _bar(2, 1.1010, 1.1016, 1.0980, 1.0990)))
    fp1 = build_setup_fingerprint(
        symbol='EURUSD',
        direction=Side.BUY.value,
        setup_type=derive_setup_type(side=Side.BUY.value, structure=first),
        structure_id=first.structure_id,
        setup_origin_timestamp=first.origin_timestamp_for_side(Side.BUY.value),
        structure_level=first.structure_level_for_side(Side.BUY.value),
        digits=5,
    )
    fp2 = build_setup_fingerprint(
        symbol='EURUSD',
        direction=Side.BUY.value,
        setup_type=derive_setup_type(side=Side.BUY.value, structure=second),
        structure_id=second.structure_id,
        setup_origin_timestamp=second.origin_timestamp_for_side(Side.BUY.value),
        structure_level=second.structure_level_for_side(Side.BUY.value),
        digits=5,
    )
    assert fp1 != fp2
    assert first.structure_id != second.structure_id


def test_fingerprint_expiry_allows_same_setup_again() -> None:
    state = InstanceState(instance=Instance(account_id='1', symbol='EURUSD', magic=1))
    fp = build_setup_fingerprint(
        symbol='EURUSD',
        direction=Side.BUY.value,
        setup_type='continuation_buy',
        structure_id='abc',
        setup_origin_timestamp='2026-07-07T06:00:00.000Z',
        structure_level=1.0990,
        digits=5,
    )
    state.register_signal_fingerprint(fp, expiry_bars=2)
    base = datetime(2026, 7, 7, 6, 0, tzinfo=timezone.utc)
    # Initialize last counted on register bar
    state.expire_signal_fingerprints(current_bar_utc=format_utc_timestamp(base))
    assert fp in state.active_signal_fingerprints
    state.expire_signal_fingerprints(current_bar_utc=format_utc_timestamp(base + timedelta(minutes=1)))
    assert fp in state.active_signal_fingerprints
    state.expire_signal_fingerprints(current_bar_utc=format_utc_timestamp(base + timedelta(minutes=2)))
    assert fp not in state.active_signal_fingerprints
    allowed = evaluate_signal_quality(**_quality_kwargs(structure_id='abc', setup_origin_timestamp='2026-07-07T06:00:00.000Z', structure_level=1.0990, active_fingerprints=state.active_signal_fingerprints))
    assert allowed.passed is True


def test_fingerprint_survives_state_restart(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_account_directories('1')
    instance = Instance(account_id='1', symbol='EURUSD', magic=1)
    state = InstanceState(instance=instance)
    fp = build_setup_fingerprint(
        symbol='EURUSD',
        direction=Side.BUY.value,
        setup_type='continuation_buy',
        structure_id='persist',
        setup_origin_timestamp='2026-07-07T06:00:00.000Z',
        structure_level=1.0990,
        digits=5,
    )
    state.register_signal_fingerprint(fp, expiry_bars=10)
    state.save(paths)
    restored = InstanceState.load(paths, instance)
    assert fp in restored.active_signal_fingerprints
    again = build_setup_fingerprint(
        symbol='EURUSD',
        direction=Side.BUY.value,
        setup_type='continuation_buy',
        structure_id='persist',
        setup_origin_timestamp='2026-07-07T06:00:00.000Z',
        structure_level=1.0990,
        digits=5,
    )
    assert again == fp


def test_score_delta_enforced_when_opposite_invalid() -> None:
    result = evaluate_signal_quality(
        **_quality_kwargs(
            buy_score=0.68,
            sell_score=0.62,
            buy_valid=True,
            sell_valid=False,
            sell_components=_sell_components(weak=False),
            signal_quality_config=_cfg(minimum_score_delta=0.15, minimum_signal_score=0.65),
        )
    )
    assert result.passed is False
    assert result.reason_code == REASON_SIGNAL_DELTA_TOO_SMALL
    assert result.score_delta == pytest.approx(0.06)


def test_build_signal_fingerprint_ignores_candle_time() -> None:
    a = build_signal_fingerprint(symbol='EURUSD', side='BUY', candle_time_utc='2026-07-07T06:01:00.000Z', structure_level=1.099, setup_type='continuation_buy', structure_id='x', setup_origin_timestamp='2026-07-07T06:00:00.000Z')
    b = build_signal_fingerprint(symbol='EURUSD', side='BUY', candle_time_utc='2026-07-07T06:05:00.000Z', structure_level=1.099, setup_type='continuation_buy', structure_id='x', setup_origin_timestamp='2026-07-07T06:00:00.000Z')
    assert a == b


@pytest.mark.parametrize(
    ('cooldown', 'loss_cooldown', 'outcome', 'blocked_count', 'allow_on'),
    [
        (0, 0, TradeOutcome.WIN.value, 0, 1),
        (1, 5, TradeOutcome.WIN.value, 1, 2),
        (3, 5, TradeOutcome.WIN.value, 3, 4),
        (3, 5, TradeOutcome.LOSS.value, 5, 6),
        (3, 5, TradeOutcome.BREAKEVEN.value, 3, 4),
        (3, 5, TradeOutcome.UNKNOWN.value, 3, 4),
    ],
)
def test_cooldown_bar_semantics(cooldown: int, loss_cooldown: int, outcome: str, blocked_count: int, allow_on: int) -> None:
    state = InstanceState(instance=Instance(account_id='1', symbol='EURUSD', magic=1))
    close_bar = datetime(2026, 7, 7, 6, 0, tzinfo=timezone.utc)
    state.register_trade_close(
        close_bar_utc=format_utc_timestamp(close_bar),
        close_time_utc=format_utc_timestamp(close_bar),
        outcome=outcome,
        cooldown_bars_after_trade=cooldown,
        cooldown_bars_after_loss=loss_cooldown,
    )
    assert state.last_trade_result == outcome
    if outcome != TradeOutcome.LOSS.value:
        assert state.last_trade_result != 'win' or outcome == TradeOutcome.WIN.value
    blocked = 0
    allowed_index = None
    for offset in range(1, 12):
        bar = close_bar + timedelta(minutes=offset)
        remaining = state.peek_cooldown_bars_remaining()
        if remaining > 0:
            blocked += 1
        else:
            allowed_index = offset
            break
        state.advance_cooldown_for_closed_bar(current_bar_utc=format_utc_timestamp(bar))
    assert blocked == blocked_count
    assert allowed_index == allow_on


def test_cooldown_restart_midway(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_account_directories('1')
    instance = Instance(account_id='1', symbol='EURUSD', magic=1)
    state = InstanceState(instance=instance)
    close_bar = datetime(2026, 7, 7, 6, 0, tzinfo=timezone.utc)
    state.register_trade_close(
        close_bar_utc=format_utc_timestamp(close_bar),
        close_time_utc=format_utc_timestamp(close_bar),
        outcome=TradeOutcome.WIN.value,
        cooldown_bars_after_trade=3,
        cooldown_bars_after_loss=5,
    )
    state.advance_cooldown_for_closed_bar(current_bar_utc=format_utc_timestamp(close_bar + timedelta(minutes=1)))
    assert state.peek_cooldown_bars_remaining() == 2
    state.save(paths)
    restored = InstanceState.load(paths, instance)
    assert restored.peek_cooldown_bars_remaining() == 2
    restored.advance_cooldown_for_closed_bar(current_bar_utc=format_utc_timestamp(close_bar + timedelta(minutes=2)))
    restored.advance_cooldown_for_closed_bar(current_bar_utc=format_utc_timestamp(close_bar + timedelta(minutes=3)))
    assert restored.peek_cooldown_bars_remaining() == 0


def test_cooldown_duplicate_candle_timestamp_decrements_once() -> None:
    state = InstanceState(instance=Instance(account_id='1', symbol='EURUSD', magic=1))
    close_bar = datetime(2026, 7, 7, 6, 0, tzinfo=timezone.utc)
    state.register_trade_close(
        close_bar_utc=format_utc_timestamp(close_bar),
        close_time_utc=format_utc_timestamp(close_bar),
        outcome=TradeOutcome.WIN.value,
        cooldown_bars_after_trade=3,
        cooldown_bars_after_loss=5,
    )
    next_bar = format_utc_timestamp(close_bar + timedelta(minutes=1))
    state.advance_cooldown_for_closed_bar(current_bar_utc=next_bar)
    state.advance_cooldown_for_closed_bar(current_bar_utc=next_bar)
    state.advance_cooldown_for_closed_bar(current_bar_utc=next_bar)
    assert state.peek_cooldown_bars_remaining() == 2


def test_cooldown_skipped_bar_still_counts_once_per_unique() -> None:
    state = InstanceState(instance=Instance(account_id='1', symbol='EURUSD', magic=1))
    close_bar = datetime(2026, 7, 7, 6, 0, tzinfo=timezone.utc)
    state.register_trade_close(
        close_bar_utc=format_utc_timestamp(close_bar),
        close_time_utc=format_utc_timestamp(close_bar),
        outcome=TradeOutcome.WIN.value,
        cooldown_bars_after_trade=3,
        cooldown_bars_after_loss=5,
    )
    # Skip minute 1; only unique later bars decrement.
    state.advance_cooldown_for_closed_bar(current_bar_utc=format_utc_timestamp(close_bar + timedelta(minutes=2)))
    assert state.peek_cooldown_bars_remaining() == 2
    state.advance_cooldown_for_closed_bar(current_bar_utc=format_utc_timestamp(close_bar + timedelta(minutes=4)))
    assert state.peek_cooldown_bars_remaining() == 1
