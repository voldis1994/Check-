from __future__ import annotations
import pytest
from engine.protocol.constants import CONFIG_SCHEMA_VERSION, PROTOCOL_SCHEMA_VERSION, STATE_SCHEMA_VERSION
from engine.protocol.errors import ValidationError
from engine.protocol.models import AckRecord, AIConfig, AnalysisConfig, AnalysisWeights, ControlCommand, DashboardConfig, DecisionJournalEntry, ErrorJournalEntry, InstanceDefinition, InstanceKey, InstanceStateRecord, JournalConfig, LoggingConfig, MarketBar, PathsConfig, RiskConfig, RuntimeConfig, SensorReading, SpreadStateRecord, StatusRecord, SystemConfig, SystemSection, TradeJournalEntry, TradeManagementSettings, UniverseRecord, validate_instance_key

def _analysis_config(**overrides: object) -> AnalysisConfig:
    weights = AnalysisWeights(momentum=1.0, trend=1.0, structure=1.0, pressure=1.0, behavior=1.0, impact=1.0, context=1.0)
    values: dict[str, object] = {'lookback_bars': 120, 'spread_relative_threshold': 1.5, 'volatility_relative_threshold': 1.5, 'block_high_impact_news': True, 'stop_loss_buffer': 0.0002, 'weights': weights}
    values.update(overrides)
    return AnalysisConfig(**values)

def _system_config() -> SystemConfig:
    return SystemConfig(schema_version=CONFIG_SCHEMA_VERSION, system=SystemSection(name='SYSTEM', root_path='C:\\Check\\System', timeframe='M1'), paths=PathsConfig(clients='data/clients', logs='data/logs', cache='data/cache', history='data/history', universe='data/universe'), runtime=RuntimeConfig(cycle_interval_ms=1000, ack_timeout_ms=5000, retry_max=3, retry_delay_ms=200, data_stale_threshold_ms=15000, cycle_max_duration_ms=30000, metrics_interval_ms=60000, auto_discover_instances=True), instances=(InstanceDefinition(account_id='12345', symbol='EURUSD', magic=100001, enabled=True),), risk=RiskConfig(max_open_positions_per_instance=1, max_daily_loss_percent=2.0, max_drawdown_percent=10.0, reward_ratio=2.0, max_risk_per_trade_percent=1.0, max_stop_loss_pips=100.0, volume_step=0.01), analysis=_analysis_config(), journal=JournalConfig(retention_days=30), trade_management=TradeManagementSettings(enabled=True, breakeven_progress_ratio=0.5, partial_close_progress_ratio=0.75, partial_close_volume_ratio=0.5, time_stop_max_bars=120), dashboard=DashboardConfig(refresh_interval_ms=1000), logging=LoggingConfig(level='INFO', format='standard'), ai=AIConfig(mode='advisory', fail_closed=False, reject_action='BLOCK', timeout_ms=10000, retry_max=2, retry_delay_ms=500))

def test_instance_key_creation_and_tuple() -> None:
    key = InstanceKey(account_id='12345', symbol='EURUSD', magic=100001)
    assert key.as_tuple() == ('12345', 'EURUSD', 100001)
    assert key.matches('12345', 'EURUSD', 100001)
    assert key.to_dict() == {'account_id': '12345', 'symbol': 'EURUSD', 'magic': 100001}

def test_instance_key_from_dict() -> None:
    key = InstanceKey.from_dict({'account_id': '999', 'symbol': 'GBPUSD', 'magic': 42})
    assert key.account_id == '999'
    assert key.symbol == 'GBPUSD'
    assert key.magic == 42

def test_validate_instance_key_helper() -> None:
    key = validate_instance_key('12345', 'EURUSD', 100001)
    assert isinstance(key, InstanceKey)

def test_instance_key_rejects_empty_account_id() -> None:
    with pytest.raises(ValidationError, match='account_id'):
        InstanceKey(account_id='', symbol='EURUSD', magic=1)

def test_instance_key_rejects_empty_symbol() -> None:
    with pytest.raises(ValidationError, match='symbol'):
        InstanceKey(account_id='12345', symbol='  ', magic=1)

def test_instance_key_rejects_negative_magic() -> None:
    with pytest.raises(ValidationError, match='magic'):
        InstanceKey(account_id='12345', symbol='EURUSD', magic=-1)

def test_instance_key_rejects_bool_magic() -> None:
    with pytest.raises(ValidationError, match='magic'):
        InstanceKey(account_id='12345', symbol='EURUSD', magic=True)

def test_instance_definition_exposes_instance_key() -> None:
    instance = InstanceDefinition(account_id='12345', symbol='EURUSD', magic=100001, enabled=True)
    assert instance.instance_key == InstanceKey('12345', 'EURUSD', 100001)

def test_instance_key_is_hashable() -> None:
    key_a = InstanceKey('12345', 'EURUSD', 1)
    key_b = InstanceKey('12345', 'EURUSD', 1)
    key_c = InstanceKey('12345', 'EURUSD', 2)
    assert key_a == key_b
    assert key_a != key_c
    assert len({key_a, key_b, key_c}) == 2

def test_system_config_required_fields() -> None:
    config = _system_config()
    data = config.to_dict()
    assert data['schema_version'] == CONFIG_SCHEMA_VERSION
    assert data['system']['name'] == 'SYSTEM'
    assert data['system']['timeframe'] == 'M1'
    assert len(data['instances']) == 1
    assert data['logging']['level'] == 'INFO'

def test_system_config_rejects_invalid_timeframe() -> None:
    with pytest.raises(ValidationError, match='timeframe'):
        SystemSection(name='SYSTEM', root_path='C:\\Check\\System', timeframe='H1')

def test_system_config_rejects_duplicate_instances() -> None:
    instance = InstanceDefinition('12345', 'EURUSD', 100001, True)
    with pytest.raises(ValidationError, match='duplicate'):
        SystemConfig(schema_version=CONFIG_SCHEMA_VERSION, system=SystemSection('SYSTEM', 'C:\\Check\\System', 'M1'), paths=PathsConfig('data/clients', 'data/logs', 'data/cache', 'data/history', 'data/universe'), runtime=RuntimeConfig(cycle_interval_ms=1000, ack_timeout_ms=5000, retry_max=3, retry_delay_ms=200, data_stale_threshold_ms=15000, cycle_max_duration_ms=30000, metrics_interval_ms=60000, auto_discover_instances=True), instances=(instance, instance), risk=RiskConfig(max_open_positions_per_instance=1, max_daily_loss_percent=2.0, max_drawdown_percent=10.0, reward_ratio=2.0, max_risk_per_trade_percent=1.0, max_stop_loss_pips=100.0, volume_step=0.01), analysis=_analysis_config(), journal=JournalConfig(30), trade_management=TradeManagementSettings(enabled=True, breakeven_progress_ratio=0.5, partial_close_progress_ratio=0.75, partial_close_volume_ratio=0.5, time_stop_max_bars=120), dashboard=DashboardConfig(1000), logging=LoggingConfig('INFO', 'standard'), ai=AIConfig(mode='advisory', fail_closed=False, reject_action='BLOCK', timeout_ms=10000, retry_max=2, retry_delay_ms=500))

def test_status_record_required_fields() -> None:
    record = StatusRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', account_id='12345', connected=True, trade_allowed=True, balance=10000.0, equity=10000.0, margin_free=9000.0, ea_version='1.0.0')
    data = record.to_dict()
    assert data['account_id'] == '12345'
    assert data['connected'] is True
    assert 'last_error' not in data

def test_universe_record_required_fields() -> None:
    record = UniverseRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', session='london', market_regime='trending', news_window_active=False)
    assert record.to_dict()['market_regime'] == 'trending'

def test_universe_record_rejects_forbidden_metadata_field() -> None:
    with pytest.raises(ValidationError, match='forbidden'):
        UniverseRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', session='london', market_regime='ranging', news_window_active=False, metadata={'signal': 'buy'})

def test_control_command_required_fields() -> None:
    command = ControlCommand(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', command_id='cmd-1', account_id='12345', symbol='EURUSD', magic=100001, action='OPEN', reason='BUY selected', decision_id='dec-1', side='BUY', volume=0.1, stop_loss=1.08, take_profit=1.09)
    assert command.instance_key.as_tuple() == ('12345', 'EURUSD', 100001)
    assert command.to_dict()['action'] == 'OPEN'

def test_ack_record_required_fields() -> None:
    record = AckRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', command_id='cmd-1', account_id='12345', symbol='EURUSD', magic=100001, status='SUCCESS', ticket=555)
    assert record.to_dict()['status'] == 'SUCCESS'

def test_instance_state_record_required_fields() -> None:
    record = InstanceStateRecord(schema_version=STATE_SCHEMA_VERSION, account_id='12345', symbol='EURUSD', magic=100001, last_decision='WAIT', last_reason='EQUAL_SCORES', last_command_id='cmd-1', last_ack_status='TIMEOUT', instrument_digits=5, instrument_point=1e-05, instrument_pip=0.0001, cycle_count=1, last_cycle_utc='2026-07-07T06:00:00.000Z')
    assert record.instance_key.symbol == 'EURUSD'

def test_spread_state_record_required_fields() -> None:
    record = SpreadStateRecord(schema_version=STATE_SCHEMA_VERSION, account_id='12345', symbol='EURUSD', magic=100001, sample_count=10, mean_spread=0.00012, std_spread=2e-05, median_spread=0.00011, current_spread=0.00013, relative_spread=0.5, updated_utc='2026-07-07T06:00:00.000Z')
    assert record.sample_count == 10

def test_decision_journal_entry_required_fields() -> None:
    entry = DecisionJournalEntry(decision_id='dec-1', timestamp_utc='2026-07-07T06:00:00.000Z', account_id='12345', symbol='EURUSD', magic=100001, decision='BUY', reason='BUY score higher', risk_result='ALLOW', buy_score=0.8, sell_score=0.3)
    assert entry.instance_key.magic == 100001

def test_trade_journal_entry_required_fields() -> None:
    entry = TradeJournalEntry(trade_id='trade-1', timestamp_utc='2026-07-07T06:00:00.000Z', account_id='12345', symbol='EURUSD', magic=100001, event='OPEN', command_id='cmd-1', ack_status='SUCCESS', reason='BUY selected', side='BUY', volume=0.1, price=1.085, ticket=555)
    assert entry.to_dict()['event'] == 'OPEN'

def test_error_journal_entry_required_fields() -> None:
    entry = ErrorJournalEntry(error_id='err-1', timestamp_utc='2026-07-07T06:00:00.000Z', account_id='12345', module='loader.market_loader', error_type='IO', message='file missing', symbol='EURUSD', magic=100001, context={'path': 'data/clients/12345/market_EURUSD_100001.csv'})
    assert entry.to_dict()['error_type'] == 'IO'

def test_market_bar_required_fields() -> None:
    bar = MarketBar(time_utc='2026-07-07T06:00:00.000Z', open=1.085, high=1.086, low=1.084, close=1.0855, volume=120.0, symbol='EURUSD', timeframe='M1', digits=5, point=1e-05)
    assert bar.to_dict()['timeframe'] == 'M1'

def test_market_bar_rejects_non_m1_timeframe() -> None:
    with pytest.raises(ValidationError, match='timeframe'):
        MarketBar(time_utc='2026-07-07T06:00:00.000Z', open=1.0, high=1.1, low=0.9, close=1.05, volume=1.0, symbol='EURUSD', timeframe='H1', digits=5, point=1e-05)

def test_sensor_reading_required_fields() -> None:
    reading = SensorReading(time_utc='2026-07-07T06:00:00.000Z', bid=1.085, ask=1.0852, spread=0.0002, spread_points=2.0, symbol='EURUSD', digits=5, point=1e-05)
    assert reading.to_dict()['spread_points'] == 2.0

def test_all_models_expose_instance_key_where_applicable() -> None:
    command = ControlCommand(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', command_id='cmd-1', account_id='12345', symbol='EURUSD', magic=100001, action='NONE', reason='WAIT', decision_id='dec-1')
    assert command.instance_key == InstanceKey('12345', 'EURUSD', 100001)
