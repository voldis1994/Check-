from __future__ import annotations
import json
from pathlib import Path
import pytest
from engine.core.config import load_system_config
from engine.core.paths import SystemPaths
from engine.protocol.constants import REASON_DUPLICATE_SIGNAL, REASON_TRADE_COOLDOWN_ACTIVE
from engine.replay.context import build_replay_universe, detect_session
from engine.replay.execution_model import ReplayExecutionConfig
from engine.replay.simulator import ReplaySimulator, run_replay
from engine.normalizer.market_normalizer import normalize_market_csv
from datetime import datetime, timezone

FIXTURES = Path(__file__).resolve().parents[1] / 'integration' / 'fixtures' / 'replay'
ROOT = Path(__file__).resolve().parents[2]


def _production_config():
    return load_system_config(ROOT / 'config' / 'system.json', system_paths=SystemPaths(ROOT))


def test_detect_session_from_timestamp() -> None:
    assert detect_session(datetime(2026, 7, 7, 6, 0, tzinfo=timezone.utc)) == 'ASIA'
    assert detect_session(datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)) == 'LONDON'
    assert detect_session(datetime(2026, 7, 7, 15, 0, tzinfo=timezone.utc)) == 'NEW_YORK'


def test_news_unavailable_not_assumed_low() -> None:
    bars = normalize_market_csv((FIXTURES / 'noise_m1_eurusd.csv').read_text(encoding='utf-8'))[:30]
    universe, meta = build_replay_universe(bars=bars, news_events=None)
    assert universe.news_impact_level is None
    assert meta['news_status'] == 'unavailable'
    assert meta['news_filter_disabled'] is True


def test_noise_fixture_mostly_wait_with_production_defaults(tmp_path: Path) -> None:
    config = _production_config()
    sq = config.signal_quality
    assert sq.minimum_signal_score == pytest.approx(0.65)
    assert sq.minimum_score_delta == pytest.approx(0.15)
    assert sq.minimum_market_quality == pytest.approx(0.60)
    assert sq.minimum_directional_confirmations == 3
    assert sq.cooldown_bars_after_trade == 3
    assert sq.cooldown_bars_after_loss == 5
    assert sq.duplicate_signal_expiry_bars == 10

    summary = run_replay(
        market_path=FIXTURES / 'noise_m1_eurusd.csv',
        config_path=ROOT / 'config' / 'system.json',
        write_signal_audit=True,
        output_dir=tmp_path / 'noise_out',
        execution=ReplayExecutionConfig(),
    )
    simulator: ReplaySimulator = summary.pop('_simulator')
    evaluated = int(summary['evaluated_bars'])
    wait = int(summary['WAIT_count'])
    assert evaluated > 0
    assert wait / evaluated >= 0.70
    # Every WAIT must carry a reason code in the audit trail.
    for row in simulator.signal_audit:
        if row['decision'] == 'WAIT':
            assert row['reason_code']
            assert str(row['reason_code']).strip()
    # No sequential same-impulse opens: fingerprint rejections or at most sparse opens.
    assert int(summary['control_files_written']) == 0
    assert not list((tmp_path / 'noise_out').glob('control_*.json'))
    # Duplicate protection engaged when opens happen, or zero opens in pure noise.
    assert int(summary['opened_trades']) <= 3
    # No look-ahead: each audit bar's universe session/regime uses only past data (checked via growing windows in simulator).
    assert (tmp_path / 'noise_out' / 'replay_summary.json').exists()
    assert (tmp_path / 'noise_out' / 'replay_trades.jsonl').exists()


def test_trend_fixture_can_produce_valid_signal_with_defaults() -> None:
    summary = run_replay(
        market_path=FIXTURES / 'trend_m1_eurusd.csv',
        config_path=ROOT / 'config' / 'system.json',
        execution=ReplayExecutionConfig(),
    )
    summary.pop('_simulator', None)
    # At least one BUY or SELL decision through the real analysis engine.
    assert int(summary['BUY_signal_count']) + int(summary['SELL_signal_count']) >= 1 or int(summary['opened_trades']) >= 1


def test_replay_never_writes_mt4_control(tmp_path: Path) -> None:
    run_replay(
        market_path=FIXTURES / 'noise_m1_eurusd.csv',
        config_path=ROOT / 'config' / 'system.json',
        output_dir=tmp_path / 'out',
    )
    clients = tmp_path / 'out'
    assert list(clients.rglob('control_*.json')) == []
    assert list(clients.rglob('ack_*.json')) == []


def test_score_delta_integration_invalid_opposite() -> None:
    from engine.decision.signal_quality import evaluate_signal_quality, default_signal_quality_dict
    from engine.protocol.models import SignalQualityConfig
    from engine.protocol.constants import REASON_SIGNAL_DELTA_TOO_SMALL

    cfg = SignalQualityConfig(**default_signal_quality_dict())
    buy = {'momentum': 0.85, 'trend': 0.82, 'structure': 0.80, 'pressure': 0.78, 'behavior': 0.75, 'impact': 0.75, 'context': 0.75}
    sell = {'momentum': 0.70, 'trend': 0.68, 'structure': 0.66, 'pressure': 0.64, 'behavior': 0.75, 'impact': 0.75, 'context': 0.75}
    result = evaluate_signal_quality(
        buy_score=0.68,
        sell_score=0.62,
        buy_valid=True,
        sell_valid=False,
        buy_components=buy,
        sell_components=sell,
        market_quality_score=0.75,
        signal_quality_config=cfg,
        symbol='EURUSD',
        candle_time_utc='2026-07-07T09:00:00.000Z',
        structure_level=1.0990,
        setup_origin_timestamp='2026-07-07T08:50:00.000Z',
        structure_id='integration-delta',
        setup_type='continuation_buy',
    )
    assert result.reason_code == REASON_SIGNAL_DELTA_TOO_SMALL
