"""Acceptance scenarios for remaining SYSTEM fixes (items 1–10 → 18 checks)."""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from engine.core.config import parse_config_payload
from engine.core.cycle import build_risk_trade_params
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.core.position_sync import _apply_status_position_to_state, reconcile_position_with_status
from engine.decision.filters.news_filter import NEWS_FILTER_INACTIVE_REASON, evaluate_news_filter
from engine.loader.closed_trade_loader import build_closed_trade_path, parse_closed_trade_payload
from engine.protocol.constants import (
    PROTOCOL_SCHEMA_VERSION,
    REASON_EXECUTION_OUTCOME_UNRESOLVED,
    REASON_STALE_STATUS_TIMESTAMP,
    REASON_STALE_UNIVERSE_TIMESTAMP,
    Decision,
    RiskResult,
)
from engine.protocol.models import RiskConfig, StatusPositionSnapshot, StatusRecord, UniverseRecord
from engine.risk.engine import RiskEngineTradeParams, run_risk_engine
from engine.risk.precheck import should_call_ai_layer as precheck_should_call_ai
from engine.state.instance_state import InstanceState
from tests.core.config_payload import valid_system_config_payload
from tests.journal.test_decision_journal import _manual_decision_result

SYSTEM_ROOT = Path(__file__).resolve().parents[2]


def _status(*, timestamp_utc: str = '2026-07-17T12:00:00.000Z', positions=()) -> StatusRecord:
    return StatusRecord(
        schema_version=PROTOCOL_SCHEMA_VERSION,
        timestamp_utc=timestamp_utc,
        account_id='12345',
        connected=True,
        trade_allowed=True,
        balance=1000.0,
        equity=1000.0,
        margin_free=900.0,
        ea_version='1.0.0',
        open_positions=positions,
    )


def _risk_config(*, fixed_lot_volume: float = 0.01) -> RiskConfig:
    return RiskConfig(
        max_open_positions_per_instance=1,
        max_daily_loss_percent=2.0,
        max_drawdown_percent=10.0,
        daily_loss_limit_enabled=False,
        drawdown_limit_enabled=False,
        reward_ratio=2.0,
        max_stop_loss_pips=100.0,
        volume_step=0.01,
        fixed_lot_volume=fixed_lot_volume,
    )


def test_01_max_risk_removed_from_active_config() -> None:
    payload = valid_system_config_payload()
    assert 'max_risk_per_trade_percent' not in payload['risk']
    config = parse_config_payload(payload)
    assert not hasattr(config.risk, 'max_risk_per_trade_percent')
    system_json = json.loads((SYSTEM_ROOT / 'config' / 'system.json').read_text(encoding='utf-8'))
    assert 'max_risk_per_trade_percent' not in system_json['risk']


def test_02_fixed_lot_required_blocks_when_zero() -> None:
    decision = _manual_decision_result()
    state = InstanceState(Instance('12345', 'EURUSD', 100001))
    state.update_instrument(digits=5, point=1e-05, pip=0.0001)
    result = run_risk_engine(
        decision_result=decision,
        risk_config=_risk_config(fixed_lot_volume=0.0),
        instance_state=state,
        status=_status(),
        trade_params=RiskEngineTradeParams(volume_step=0.01, max_stop_loss_pips=100.0),
        swing_low=1.0995,
        swing_high=1.12,
        use_fixed_take_profit=False,
    )
    assert result.result == RiskResult.BLOCK.value
    assert 'fixed_lot_volume' in result.reason


def test_03_risk_engine_never_calls_calculate_position_size() -> None:
    source = inspect.getsource(run_risk_engine)
    assert 'calculate_position_size' not in source
    assert 'fixed_lot_volume' in source


def test_04_stale_status_reason_constant_and_cycle_gate() -> None:
    cycle_src = (SYSTEM_ROOT / 'engine' / 'core' / 'cycle.py').read_text(encoding='utf-8')
    assert 'status_content_freshness_ms' in cycle_src
    assert 'REASON_STALE_STATUS_TIMESTAMP' in cycle_src
    assert 'stale status timestamp' in cycle_src
    # stale status blocks reconcile + TM + OPEN
    assert 'if not status_stale:' in cycle_src
    assert 'management_blocked = status_stale' in cycle_src


def test_05_stale_status_still_allows_observability_path() -> None:
    cycle_src = (SYSTEM_ROOT / 'engine' / 'core' / 'cycle.py').read_text(encoding='utf-8')
    # Cycle continues after stale status log (decision/journal still run)
    assert 'stale status timestamp' in cycle_src
    assert 'run_instance_decision_phase' in cycle_src
    assert 'log_decision' in cycle_src


def test_06_stale_universe_blocks_entry_not_trailing() -> None:
    cycle_src = (SYSTEM_ROOT / 'engine' / 'core' / 'cycle.py').read_text(encoding='utf-8')
    assert 'REASON_STALE_UNIVERSE_TIMESTAMP' in cycle_src
    assert 'universe_stale' in cycle_src
    # Trailing/TM is gated by status_stale/sensor, not universe_stale alone
    assert 'management_blocked = status_stale or stale_sensor_blocks_trailing' in cycle_src
    assert 'stale universe blocks new entry' in cycle_src


def test_07_closed_trade_match_journals_real_close(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    instance = Instance('12345', 'EURUSD', 100001)
    paths.ensure_account_directories(instance.account_id)
    closed_path = build_closed_trade_path(paths, instance)
    closed_path.write_text(
        json.dumps(
            {
                'account_id': '12345',
                'symbol': 'EURUSD',
                'magic': 100001,
                'ticket': 42,
                'close_price': 1.1055,
                'close_time_utc': '2026-07-17T12:05:00.000Z',
                'profit': 12.5,
                'commission': -0.2,
                'swap': -0.1,
                'close_reason': 'stop_loss',
            }
        ),
        encoding='utf-8',
    )
    state = InstanceState(instance)
    state.update_position(open_ticket=42, position_side='BUY', position_volume=0.01, entry_price=1.1, stop_loss=1.09)
    status = _status(positions=())
    result = reconcile_position_with_status(paths, instance, state, status, timestamp_utc='2026-07-17T12:06:00.000Z')
    assert result.close_reconciled is True
    assert state.close_pending_reconciliation is False
    journal = list((paths.account_journal_dir(instance.account_id)).glob('trade_*.jsonl'))
    assert journal
    line = journal[0].read_text(encoding='utf-8').strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload['price'] == pytest.approx(1.1055)
    assert 'profit=12.5' in payload['reason'] or '12.5' in payload['reason']
    assert 'commission' in payload['reason']
    assert 'swap' in payload['reason']


def test_08_close_pending_kept_when_closed_file_missing(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    instance = Instance('12345', 'EURUSD', 100001)
    paths.ensure_account_directories(instance.account_id)
    state = InstanceState(instance)
    state.update_position(open_ticket=77, position_side='SELL', position_volume=0.02, entry_price=1.2, stop_loss=1.21)
    result = reconcile_position_with_status(paths, instance, state, _status(positions=()), timestamp_utc='2026-07-17T12:06:00.000Z')
    assert result.close_pending is True
    assert state.close_pending_reconciliation is True
    assert state.close_pending_ticket == 77
    assert state.open_ticket is None
    # Still pending next cycle
    result2 = reconcile_position_with_status(paths, instance, state, _status(positions=()), timestamp_utc='2026-07-17T12:07:00.000Z')
    assert state.close_pending_reconciliation is True
    assert result2.close_reconciled is False


def test_09_never_invent_sl_or_entry_as_close_price(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    instance = Instance('12345', 'EURUSD', 100001)
    paths.ensure_account_directories(instance.account_id)
    state = InstanceState(instance)
    state.update_position(open_ticket=9, position_side='BUY', position_volume=0.01, entry_price=1.1000, stop_loss=1.0900)
    reconcile_position_with_status(paths, instance, state, _status(positions=()), timestamp_utc='2026-07-17T12:06:00.000Z')
    journal_files = list(paths.account_journal_dir(instance.account_id).glob('trade_*.jsonl'))
    for path in journal_files:
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            assert payload.get('price') not in {1.1, 1.1000, 1.09, 1.0900}


def test_10_cycle_order_tm_before_ai() -> None:
    src = (SYSTEM_ROOT / 'engine' / 'core' / 'cycle.py').read_text(encoding='utf-8')
    tm_pos = src.find('run_instance_trade_management_phase')
    decision_pos = src.find('Entry decision analysis AFTER trade management')
    ai_pos = src.find('run_instance_ai_risk_pipeline(decision_result=decision_result, instance_memory=instance_memory, status=status')
    assert tm_pos > 0 and decision_pos > tm_pos
    assert ai_pos > decision_pos


def test_11_ai_not_called_on_wait() -> None:
    from engine.protocol.models import StatusRecord
    from engine.core.instance import Instance as Inst
    decision = _manual_decision_result()
    # Force WAIT
    wait = decision.__class__(
        decision_id=decision.decision_id,
        decision=Decision.WAIT.value,
        reason='WAIT: equal scores',
        preferred_side=decision.preferred_side,
        buy_candidate=decision.buy_candidate,
        sell_candidate=decision.sell_candidate,
        buy_score=decision.buy_score,
        sell_score=decision.sell_score,
        analysis_context=decision.analysis_context,
    )
    state = InstanceState(Inst('12345', 'EURUSD', 100001))
    assert precheck_should_call_ai(decision_result=wait, status=_status(), instance_state=state, risk_config=_risk_config()) is False


def test_12_ai_not_called_for_trailing_non_entry() -> None:
    # Trailing never goes through should_call_ai with BUY/SELL from TM; precheck requires BUY/SELL.
    from engine.core.instance import Instance as Inst
    decision = _manual_decision_result()
    block = decision.__class__(
        decision_id=decision.decision_id,
        decision=Decision.BLOCK.value,
        reason='BLOCK: x',
        preferred_side=decision.preferred_side,
        buy_candidate=decision.buy_candidate,
        sell_candidate=decision.sell_candidate,
        buy_score=decision.buy_score,
        sell_score=decision.sell_score,
        analysis_context=decision.analysis_context,
    )
    state = InstanceState(Inst('12345', 'EURUSD', 100001))
    assert precheck_should_call_ai(decision_result=block, status=_status(), instance_state=state, risk_config=_risk_config()) is False


def test_13_ai_timeout_ms_is_2500() -> None:
    system_json = json.loads((SYSTEM_ROOT / 'config' / 'system.json').read_text(encoding='utf-8'))
    assert system_json['ai']['timeout_ms'] == 2500
    payload = valid_system_config_payload()
    assert payload['ai']['timeout_ms'] == 2500


def test_14_pending_execution_blocks_open_reason() -> None:
    from engine.reason import build_reason
    reason = build_reason(REASON_EXECUTION_OUTCOME_UNRESOLVED, 'pending execution outcome blocks new OPEN', pending_command_id='cmd-x')
    assert REASON_EXECUTION_OUTCOME_UNRESOLVED in reason
    cycle_src = (SYSTEM_ROOT / 'engine' / 'core' / 'cycle.py').read_text(encoding='utf-8')
    assert 'pending_execution_command_id is not None' in cycle_src
    assert 'REASON_EXECUTION_OUTCOME_UNRESOLVED' in cycle_src


def test_15_ack_timeout_sets_pending_does_not_clear() -> None:
    exec_src = (SYSTEM_ROOT / 'engine' / 'execution' / 'engine.py').read_text(encoding='utf-8')
    assert 'instance_state.pending_execution_command_id = order_command.command_id' in exec_src
    # Timeout path must not clear pending
    timeout_block = exec_src.split('if not ack_ready:')[1].split('ack_record = read_ack_for_command')[0]
    assert 'pending_execution_command_id = None' not in timeout_block


def test_16_ack_timeout_status_reconcile_confirms_broker(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    instance = Instance('12345', 'EURUSD', 100001)
    paths.ensure_account_directories(instance.account_id)
    state = InstanceState(instance)
    state.instrument_digits = 5
    state.instrument_point = 0.00001
    state.pending_execution_command_id = 'pending-open'
    status = _status(
        positions=(
            StatusPositionSnapshot(
                symbol='EURUSD',
                magic=100001,
                ticket=555,
                side='BUY',
                volume=0.01,
                entry_price=1.1003,
                stop_loss=1.09,
                take_profit=0.0,
                open_time_utc='2026-07-17T12:00:01.000Z',
            ),
        )
    )
    result = reconcile_position_with_status(paths, instance, state, status, timestamp_utc='2026-07-17T12:00:05.000Z')
    assert result.broker_execution_confirmed is True
    assert state.open_ticket == 555
    assert state.position_entry_price == pytest.approx(1.1003)
    assert state.pending_execution_command_id is None


def test_17_apply_status_position_deduplicated() -> None:
    source = inspect.getsource(_apply_status_position_to_state)
    # Entry price assignment should appear once in the else-branch path, not duplicated after.
    assert source.count('instance_state.position_entry_price = position.entry_price') == 1


def test_18_news_filter_inactive_when_disabled() -> None:
    system_json = json.loads((SYSTEM_ROOT / 'config' / 'system.json').read_text(encoding='utf-8'))
    assert system_json['analysis']['block_high_impact_news'] is False
    universe = UniverseRecord(
        schema_version=PROTOCOL_SCHEMA_VERSION,
        timestamp_utc='2026-07-17T12:00:00.000Z',
        session='LONDON',
        market_regime='ranging',
        news_window_active=True,
        news_impact_level='high',
        metadata={'news_data_available': False, 'news_filter': 'disabled_no_calendar'},
    )
    result = evaluate_news_filter(universe, block_high_impact_news=False)
    assert result.news_acceptable is True
    assert result.reason == NEWS_FILTER_INACTIVE_REASON
    cycle_src = (SYSTEM_ROOT / 'engine' / 'core' / 'cycle.py').read_text(encoding='utf-8')
    assert 'news filter inactive' in cycle_src


def test_closed_trade_parser_fields() -> None:
    record = parse_closed_trade_payload(
        {
            'account_id': '1',
            'symbol': 'EURUSD',
            'magic': 1,
            'ticket': 9,
            'close_price': 1.2,
            'close_time_utc': '2026-07-17T12:00:00.000Z',
            'profit': 1.0,
            'commission': -0.1,
            'swap': 0.0,
        }
    )
    assert record.ticket == 9
    assert record.close_price == pytest.approx(1.2)


def test_risk_trade_params_have_no_max_risk(tmp_path: Path) -> None:
    from engine.core.lifecycle import startup
    from tests.core.test_cycle import _write_config, _install_valid_fixtures

    config_path = _write_config(tmp_path)
    instance = Instance('12345', 'EURUSD', 100001)
    _install_valid_fixtures(SystemPaths(tmp_path), instance)
    runtime = startup(root_path=tmp_path, config_path=config_path)
    params = build_risk_trade_params(runtime)
    assert not hasattr(params, 'max_risk_per_trade_percent')
