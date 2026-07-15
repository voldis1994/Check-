from __future__ import annotations
import pytest
from engine.ai_decision_layer import get_ai_decision
from engine.normalizer.spread_model import update_spread_model
from engine.protocol.constants import OrderAction
from engine.risk.precheck import should_call_ai_layer
from engine.risk.trade_management import OpenPosition, TradeManagementConfig, evaluate_trade_management
from tests.ai.test_ai_decision_layer import _advisory_config
from tests.journal.test_decision_journal import _manual_decision_result

def test_single_sample_spread_uses_neutral_relative_spread() -> None:
    snapshot = update_spread_model((), current_spread=0.0002, lookback_bars=10)
    assert snapshot.sample_count == 1
    assert snapshot.relative_spread == pytest.approx(1.0)

def test_should_skip_ai_when_risk_rules_block_buy() -> None:
    from engine.protocol.models import StatusRecord
    from engine.protocol.constants import PROTOCOL_SCHEMA_VERSION
    from engine.state.instance_state import InstanceState
    from engine.core.paths import SystemPaths
    from engine.core.instance import Instance
    from tests.core.config_payload import valid_system_config_payload
    from engine.core.config import parse_config_payload
    config = parse_config_payload(valid_system_config_payload())
    status = StatusRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', account_id='12345', connected=True, trade_allowed=True, balance=10000.0, equity=10000.0, margin_free=9000.0, ea_version='1.0.0')
    paths = SystemPaths('/tmp')
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    state = InstanceState.load(paths, instance)
    state.update_position(open_ticket=1001, position_side='BUY', position_volume=0.1)
    decision = _manual_decision_result()
    assert not should_call_ai_layer(decision_result=decision, status=status, instance_state=state, risk_config=config.risk)

def test_trade_management_close_disabled_blocks_time_stop_close() -> None:
    # Price not yet favorable for BE/trail — close remains disabled, no MODIFY either.
    position = OpenPosition(ticket=1001, side='BUY', entry_price=1.1, stop_loss=1.095, take_profit=1.11, volume=0.1, bars_open=200, partial_close_applied=False)
    config = TradeManagementConfig(breakeven_progress_ratio=0.5, trailing_buffer=0.0002, partial_close_progress_ratio=0.75, partial_close_volume_ratio=0.5, time_stop_max_bars=120, volume_step=0.01)
    result = evaluate_trade_management(position=position, current_price=1.1005, swing_low=1.09, swing_high=1.11, config=config, digits=5, allow_close=False)
    assert result.action == OrderAction.NONE.value


def test_trade_management_close_disabled_still_trails_after_time_stop() -> None:
    # Trailing must keep working when CLOSE is gated by allow_close=false.
    position = OpenPosition(ticket=1001, side='BUY', entry_price=1.1, stop_loss=1.095, take_profit=1.12, volume=0.1, bars_open=200, partial_close_applied=False)
    config = TradeManagementConfig(breakeven_progress_ratio=0.95, trailing_buffer=0.0002, partial_close_progress_ratio=0.95, partial_close_volume_ratio=0.5, time_stop_max_bars=30, volume_step=0.01, price_trail_distance=0.0005)
    result = evaluate_trade_management(position=position, current_price=1.108, swing_low=1.104, swing_high=1.11, config=config, digits=5, allow_close=False, use_fixed_take_profit=False)
    assert result.action == OrderAction.MODIFY.value
    assert 'TRAILING' in result.reason

def test_get_ai_decision_honors_skip_reason() -> None:
    result = get_ai_decision(system_signal='BUY', market_context={}, ai_config=_advisory_config(), skip_reason='skipped_risk_precheck')
    assert result.decision is None
    assert result.error_type == 'skipped_risk_precheck'
