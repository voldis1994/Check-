from __future__ import annotations
import json
import pytest
from engine.protocol.constants import CONFIG_SCHEMA_VERSION, PROTOCOL_SCHEMA_VERSION, STATE_SCHEMA_VERSION
from engine.protocol.errors import ProtocolError
from engine.protocol.models import AckRecord, AIConfig, AnalysisConfig, AnalysisWeights, ControlCommand, DashboardConfig, DecisionJournalEntry, ErrorJournalEntry, InstanceDefinition, InstanceStateRecord, JournalConfig, LoggingConfig, MarketBar, PathsConfig, RiskConfig, RuntimeConfig, SensorReading, SpreadStateRecord, StatusRecord, SystemConfig, SystemSection, TradeJournalEntry, TradeManagementSettings, UniverseRecord
from engine.protocol.parser import parse_ack, parse_control, parse_decision_journal_line, parse_error_journal_line, parse_instance_state, parse_json, parse_market_csv, parse_sensor_csv, parse_spread_state, parse_status, parse_system_config, parse_trade_journal_line, parse_universe
from engine.protocol.writer import ACK_REQUIRED_FIELDS, CONTROL_REQUIRED_FIELDS, DECISION_JOURNAL_REQUIRED_FIELDS, ERROR_JOURNAL_REQUIRED_FIELDS, INSTANCE_STATE_REQUIRED_FIELDS, SPREAD_STATE_REQUIRED_FIELDS, STATUS_REQUIRED_FIELDS, SYSTEM_CONFIG_REQUIRED_FIELDS, TRADE_JOURNAL_REQUIRED_FIELDS, UNIVERSE_REQUIRED_FIELDS, required_fields_present, write_ack, write_control, write_decision_journal_entry, write_error_journal_entry, write_instance_state, write_jsonl_line, write_market_csv, write_sensor_csv, write_spread_state, write_status, write_system_config, write_trade_journal_entry, write_universe

def _system_config() -> SystemConfig:
    return SystemConfig(schema_version=CONFIG_SCHEMA_VERSION, system=SystemSection(name='SYSTEM', root_path='C:\\Check\\System', timeframe='M1'), paths=PathsConfig(clients='data/clients', logs='data/logs', cache='data/cache', history='data/history', universe='data/universe'), runtime=RuntimeConfig(cycle_interval_ms=1000, ack_timeout_ms=5000, retry_max=3, retry_delay_ms=200, data_stale_threshold_ms=15000, cycle_max_duration_ms=30000, metrics_interval_ms=60000, auto_discover_instances=True, execute_entries_on_closed_bar_only=True), instances=(InstanceDefinition(account_id='12345', symbol='EURUSD', magic=100001, enabled=True),), risk=RiskConfig(max_open_positions_per_instance=1, max_daily_loss_percent=2.0, max_drawdown_percent=10.0, daily_loss_limit_enabled=True, drawdown_limit_enabled=True, reward_ratio=2.0, max_risk_per_trade_percent=1.0, max_stop_loss_pips=100.0, volume_step=0.01, fixed_lot_volume=0.0), analysis=AnalysisConfig(lookback_bars=120, spread_relative_threshold=1.5, volatility_relative_threshold=1.5, block_high_impact_news=True, stop_loss_buffer=0.0002, weights=AnalysisWeights(momentum=1.0, trend=1.0, structure=1.0, pressure=1.0, behavior=1.0, impact=1.0, context=1.0)), journal=JournalConfig(retention_days=30), trade_management=TradeManagementSettings(enabled=True, allow_close=True, breakeven_progress_ratio=0.5, partial_close_progress_ratio=0.75, partial_close_volume_ratio=0.5, time_stop_max_bars=120), dashboard=DashboardConfig(refresh_interval_ms=1000), logging=LoggingConfig(level='INFO', format='standard'), ai=AIConfig(mode='advisory', fail_closed=False, reject_action='BLOCK', timeout_ms=10000, retry_max=2, retry_delay_ms=500))

def _status_record() -> StatusRecord:
    return StatusRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', account_id='12345', connected=True, trade_allowed=True, balance=10000.0, equity=10000.0, margin_free=9000.0, ea_version='1.0.0', last_error='none')

def _universe_record() -> UniverseRecord:
    return UniverseRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', session='london', market_regime='trending', news_window_active=False, news_impact_level='low', correlation_group={'EURUSD': 'majors'}, metadata={'note': 'context only'})

def _control_command() -> ControlCommand:
    return ControlCommand(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', command_id='cmd-1', account_id='12345', symbol='EURUSD', magic=100001, action='OPEN', reason='BUY selected', decision_id='dec-1', side='BUY', volume=0.1, stop_loss=1.08, take_profit=1.09)

def _ack_record() -> AckRecord:
    return AckRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', command_id='cmd-1', account_id='12345', symbol='EURUSD', magic=100001, status='SUCCESS', ticket=555, error_code=0, error_message='ok')

def _instance_state_record() -> InstanceStateRecord:
    return InstanceStateRecord(schema_version=STATE_SCHEMA_VERSION, account_id='12345', symbol='EURUSD', magic=100001, last_decision='WAIT', last_reason='EQUAL_SCORES', last_command_id='cmd-1', last_ack_status='TIMEOUT', instrument_digits=5, instrument_point=1e-05, instrument_pip=0.0001, cycle_count=7, last_cycle_utc='2026-07-07T06:00:00.000Z', open_ticket=555, position_side='BUY', position_volume=0.1)

def _spread_state_record() -> SpreadStateRecord:
    return SpreadStateRecord(schema_version=STATE_SCHEMA_VERSION, account_id='12345', symbol='EURUSD', magic=100001, sample_count=10, mean_spread=0.00012, std_spread=2e-05, median_spread=0.00011, current_spread=0.00013, relative_spread=0.5, updated_utc='2026-07-07T06:00:00.000Z')

def _decision_journal_entry() -> DecisionJournalEntry:
    return DecisionJournalEntry(decision_id='dec-1', timestamp_utc='2026-07-07T06:00:00.000Z', account_id='12345', symbol='EURUSD', magic=100001, decision='BUY', reason='BUY score higher', risk_result='ALLOW', buy_score=0.8, sell_score=0.3, risk_reason=None)

def _trade_journal_entry() -> TradeJournalEntry:
    return TradeJournalEntry(trade_id='trade-1', timestamp_utc='2026-07-07T06:00:00.000Z', account_id='12345', symbol='EURUSD', magic=100001, event='OPEN', command_id='cmd-1', ack_status='SUCCESS', reason='BUY selected', side='BUY', volume=0.1, price=1.085, ticket=555)

def _error_journal_entry() -> ErrorJournalEntry:
    return ErrorJournalEntry(error_id='err-1', timestamp_utc='2026-07-07T06:00:00.000Z', account_id='12345', module='loader.market_loader', error_type='IO', message='file missing', symbol='EURUSD', magic=100001, context={'path': 'data/clients/12345/market_EURUSD_100001.csv'})

def _market_bars() -> tuple[MarketBar, ...]:
    return (MarketBar(time_utc='2026-07-07T06:00:00.000Z', open=1.085, high=1.086, low=1.084, close=1.0855, volume=120.0, symbol='EURUSD', timeframe='M1', digits=5, point=1e-05), MarketBar(time_utc='2026-07-07T06:01:00.000Z', open=1.0855, high=1.0865, low=1.085, close=1.086, volume=98.0, symbol='EURUSD', timeframe='M1', digits=5, point=1e-05))

def _sensor_readings() -> tuple[SensorReading, ...]:
    return (SensorReading(time_utc='2026-07-07T06:00:00.000Z', bid=1.085, ask=1.0852, spread=0.0002, spread_points=2.0, symbol='EURUSD', digits=5, point=1e-05),)

def test_round_trip_system_config() -> None:
    original = _system_config()
    restored = parse_system_config(write_system_config(original))
    assert restored == original

def test_round_trip_status() -> None:
    original = _status_record()
    restored = parse_status(write_status(original))
    assert restored == original

def test_round_trip_universe() -> None:
    original = _universe_record()
    restored = parse_universe(write_universe(original))
    assert restored == original

def test_round_trip_control() -> None:
    original = _control_command()
    restored = parse_control(write_control(original))
    assert restored == original

def test_round_trip_ack() -> None:
    original = _ack_record()
    restored = parse_ack(write_ack(original))
    assert restored == original

def test_round_trip_instance_state() -> None:
    original = _instance_state_record()
    restored = parse_instance_state(write_instance_state(original))
    assert restored == original

def test_round_trip_spread_state() -> None:
    original = _spread_state_record()
    restored = parse_spread_state(write_spread_state(original))
    assert restored == original

def test_round_trip_market_csv() -> None:
    original = _market_bars()
    restored = parse_market_csv(write_market_csv(original))
    assert restored == original

def test_round_trip_sensor_csv() -> None:
    original = _sensor_readings()
    restored = parse_sensor_csv(write_sensor_csv(original))
    assert restored == original

def test_round_trip_decision_journal_line() -> None:
    original = _decision_journal_entry()
    restored = parse_decision_journal_line(write_decision_journal_entry(original))
    assert restored == original

def test_round_trip_trade_journal_line() -> None:
    original = _trade_journal_entry()
    restored = parse_trade_journal_line(write_trade_journal_entry(original))
    assert restored == original

def test_round_trip_error_journal_line() -> None:
    original = _error_journal_entry()
    restored = parse_error_journal_line(write_error_journal_entry(original))
    assert restored == original

def test_jsonl_line_format_decision_journal() -> None:
    line = write_decision_journal_entry(_decision_journal_entry())
    assert '\n' not in line
    assert '\r' not in line
    parsed = json.loads(line)
    assert isinstance(parsed, dict)
    assert parsed['decision_id'] == 'dec-1'

def test_jsonl_line_format_trade_journal() -> None:
    line = write_trade_journal_entry(_trade_journal_entry())
    assert '\n' not in line
    parsed = json.loads(line)
    assert parsed['event'] == 'OPEN'

def test_jsonl_line_format_error_journal() -> None:
    line = write_error_journal_entry(_error_journal_entry())
    assert '\n' not in line
    parsed = json.loads(line)
    assert parsed['error_type'] == 'IO'

def test_jsonl_line_rejects_embedded_newlines() -> None:
    with pytest.raises(ProtocolError, match='newline'):
        write_jsonl_line({'message': 'bad\nvalue'})

def test_status_required_fields_in_output() -> None:
    data = parse_json(write_status(_status_record()))
    assert required_fields_present(data, STATUS_REQUIRED_FIELDS)

def test_universe_required_fields_in_output() -> None:
    data = parse_json(write_universe(_universe_record()))
    assert required_fields_present(data, UNIVERSE_REQUIRED_FIELDS)

def test_control_required_fields_in_output() -> None:
    data = parse_json(write_control(_control_command()))
    assert required_fields_present(data, CONTROL_REQUIRED_FIELDS)

def test_ack_required_fields_in_output() -> None:
    data = parse_json(write_ack(_ack_record()))
    assert required_fields_present(data, ACK_REQUIRED_FIELDS)

def test_system_config_required_fields_in_output() -> None:
    data = parse_json(write_system_config(_system_config()))
    assert required_fields_present(data, SYSTEM_CONFIG_REQUIRED_FIELDS)

def test_instance_state_required_fields_in_output() -> None:
    data = parse_json(write_instance_state(_instance_state_record()))
    assert required_fields_present(data, INSTANCE_STATE_REQUIRED_FIELDS)

def test_spread_state_required_fields_in_output() -> None:
    data = parse_json(write_spread_state(_spread_state_record()))
    assert required_fields_present(data, SPREAD_STATE_REQUIRED_FIELDS)

def test_decision_journal_required_fields_in_output() -> None:
    data = json.loads(write_decision_journal_entry(_decision_journal_entry()))
    assert required_fields_present(data, DECISION_JOURNAL_REQUIRED_FIELDS)

def test_trade_journal_required_fields_in_output() -> None:
    data = json.loads(write_trade_journal_entry(_trade_journal_entry()))
    assert required_fields_present(data, TRADE_JOURNAL_REQUIRED_FIELDS)

def test_error_journal_required_fields_in_output() -> None:
    data = json.loads(write_error_journal_entry(_error_journal_entry()))
    assert required_fields_present(data, ERROR_JOURNAL_REQUIRED_FIELDS)

def test_market_csv_header_matches_specification() -> None:
    csv_text = write_market_csv(_market_bars())
    header = csv_text.splitlines()[0]
    assert header == 'time_utc,open,high,low,close,volume,symbol,timeframe,digits,point'

def test_sensor_csv_header_matches_specification() -> None:
    csv_text = write_sensor_csv(_sensor_readings())
    header = csv_text.splitlines()[0]
    assert header == 'time_utc,bid,ask,spread,spread_points,symbol,digits,point'
