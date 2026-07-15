from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import pytest
from engine.core.config import load_system_config, parse_config_payload
from engine.core.paths import SystemPaths
from engine.protocol.constants import CONFIG_SCHEMA_VERSION
from engine.protocol.errors import ConfigurationError
from tests.core.config_payload import valid_system_config_payload

def test_parse_config_payload_valid_config_loads() -> None:
    config = parse_config_payload(valid_system_config_payload())
    assert config.schema_version == CONFIG_SCHEMA_VERSION
    assert config.system.timeframe == 'M1'
    assert len(config.instances) == 1

def test_parse_config_payload_loads_analysis_and_risk_decision_parameters() -> None:
    config = parse_config_payload(valid_system_config_payload())
    assert config.analysis.spread_relative_threshold == 1.5
    assert config.analysis.volatility_relative_threshold == 1.5
    assert config.analysis.block_high_impact_news is True
    assert config.analysis.stop_loss_buffer == 0.0002
    assert config.analysis.weights.momentum == 1.0
    assert config.risk.reward_ratio == 2.0
    assert config.risk.max_risk_per_trade_percent == 1.0
    assert config.risk.max_stop_loss_pips == 100.0
    assert config.risk.volume_step == 0.01

def test_parse_config_payload_missing_required_field_raises() -> None:
    payload = valid_system_config_payload()
    del payload['runtime']['ack_timeout_ms']
    with pytest.raises(ConfigurationError, match='unsupported fields|invalid config payload'):
        parse_config_payload(payload)

def test_parse_config_payload_missing_analysis_weight_raises_clear_error() -> None:
    payload = valid_system_config_payload()
    del payload['analysis']['weights']['momentum']
    with pytest.raises(ConfigurationError, match='unsupported fields|invalid config payload|momentum'):
        parse_config_payload(payload)

def test_parse_config_payload_missing_reward_ratio_raises_clear_error() -> None:
    payload = valid_system_config_payload()
    del payload['risk']['reward_ratio']
    with pytest.raises(ConfigurationError, match='unsupported fields|invalid config payload|reward_ratio'):
        parse_config_payload(payload)

def test_parse_config_payload_non_m1_timeframe_raises() -> None:
    payload = valid_system_config_payload()
    payload['system']['timeframe'] = 'H1'
    with pytest.raises(ConfigurationError, match='invalid config payload'):
        parse_config_payload(payload)

def test_parse_config_payload_hard_spread_limits_rejected() -> None:
    payload = valid_system_config_payload()
    payload['risk']['max_spread_points'] = 30
    with pytest.raises(ConfigurationError, match='hard spread limits'):
        parse_config_payload(payload)

def test_parse_config_payload_hard_symbol_list_rejected() -> None:
    payload = valid_system_config_payload()
    payload['analysis']['symbols'] = ['EURUSD', 'GBPUSD']
    with pytest.raises(ConfigurationError, match='hard symbol lists'):
        parse_config_payload(payload)

def test_load_system_config_reads_file_successfully(tmp_path: Path) -> None:
    config_path = tmp_path / 'system.json'
    config_path.write_text(json.dumps(valid_system_config_payload()), encoding='utf-8')
    config = load_system_config(config_path)
    assert config.system.name == 'SYSTEM'

def test_load_system_config_uses_system_paths_default(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.config_path.parent.mkdir(parents=True, exist_ok=True)
    paths.config_path.write_text(json.dumps(valid_system_config_payload()), encoding='utf-8')
    config = load_system_config(system_paths=paths)
    assert config.paths.clients == 'data/clients'

def test_load_system_config_invalid_json_raises(tmp_path: Path) -> None:
    config_path = tmp_path / 'system.json'
    config_path.write_text('{invalid-json', encoding='utf-8')
    with pytest.raises(ConfigurationError, match='invalid JSON'):
        load_system_config(config_path)

def test_load_system_config_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match='failed to read config file'):
        load_system_config(tmp_path / 'missing.json')

def test_load_system_config_repository_file() -> None:
    config = load_system_config(Path('config/system.json'))
    assert config.schema_version == CONFIG_SCHEMA_VERSION
    assert config.system.name == 'SYSTEM'
    assert config.system.timeframe == 'M1'
    assert config.paths.clients == 'data/clients'
    assert config.analysis.weights.context == 1.0
    assert config.risk.reward_ratio == 2.0
    assert config.trade_management.trailing_mode == 'atr_multiple'
    assert config.trade_management.trailing_lookback_bars == 8
    assert config.trade_management.trailing_step_pips == 4.0
    assert config.trade_management.trailing_atr_mult == 1.2
    assert config.trade_management.trailing_spread_floor_mult == 1.2

def test_parse_config_payload_loads_universal_trailing_settings() -> None:
    config = parse_config_payload(valid_system_config_payload())
    assert config.trade_management.trailing_mode == 'fixed_pips'
    assert config.trade_management.trailing_atr_mult == 1.2
    assert config.trade_management.trailing_atr_period == 14
    assert config.trade_management.trailing_sl_fraction == 0.5
    assert config.trade_management.trailing_spread_floor_mult == 1.2

def test_parse_config_payload_allows_instance_trailing_overrides() -> None:
    payload = valid_system_config_payload()
    payload['instances'][0]['trailing_mode'] = 'atr_multiple'
    payload['instances'][0]['trailing_step_pips'] = 3.0
    payload['instances'][0]['trailing_lookback_bars'] = 12
    payload['instances'][0]['trailing_spread_floor_mult'] = 1.5
    payload['instances'][0]['stop_loss_buffer'] = 0.5
    config = parse_config_payload(payload)
    instance = config.instances[0]
    assert instance.trailing_mode == 'atr_multiple'
    assert instance.trailing_step_pips == 3.0
    assert instance.trailing_lookback_bars == 12
    assert instance.trailing_spread_floor_mult == 1.5
    assert instance.stop_loss_buffer == 0.5

def test_parse_config_payload_rejects_unknown_instance_fields() -> None:
    payload = valid_system_config_payload()
    payload['instances'][0]['unknown_field'] = 1
    with pytest.raises(ConfigurationError, match='unsupported fields'):
        parse_config_payload(payload)

def test_parse_config_payload_rejects_invalid_trailing_mode() -> None:
    payload = valid_system_config_payload()
    payload['trade_management']['trailing_mode'] = 'magic'
    with pytest.raises(ConfigurationError, match='invalid config payload'):
        parse_config_payload(payload)
