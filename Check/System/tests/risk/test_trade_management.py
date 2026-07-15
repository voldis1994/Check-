from __future__ import annotations
import pytest
from engine.protocol.constants import Decision, OrderAction, Side
from engine.protocol.errors import ValidationError
from engine.risk.trade_management import OpenPosition, TradeManagementConfig, TradeManagementResult, compute_progress_to_take_profit, evaluate_breakeven, evaluate_partial_close, evaluate_time_stop, evaluate_trade_management, evaluate_trailing_stop

def _config() -> TradeManagementConfig:
    return TradeManagementConfig(breakeven_progress_ratio=0.5, trailing_buffer=0.0002, partial_close_progress_ratio=0.75, partial_close_volume_ratio=0.5, time_stop_max_bars=120, volume_step=0.01)

def _buy_position(*, entry_price: float=1.1, stop_loss: float=1.098, take_profit: float=1.104, volume: float=0.1, bars_open: int=10, partial_close_applied: bool=False) -> OpenPosition:
    return OpenPosition(ticket=1001, side=Side.BUY.value, entry_price=entry_price, stop_loss=stop_loss, take_profit=take_profit, volume=volume, bars_open=bars_open, partial_close_applied=partial_close_applied)

def _sell_position(*, entry_price: float=1.105, stop_loss: float=1.107, take_profit: float=1.101, volume: float=0.1, bars_open: int=10, partial_close_applied: bool=False) -> OpenPosition:
    return OpenPosition(ticket=1002, side=Side.SELL.value, entry_price=entry_price, stop_loss=stop_loss, take_profit=take_profit, volume=volume, bars_open=bars_open, partial_close_applied=partial_close_applied)

def test_compute_progress_to_take_profit_for_buy_and_sell() -> None:
    buy_progress = compute_progress_to_take_profit(side=Side.BUY.value, entry_price=1.1, take_profit=1.104, current_price=1.102)
    sell_progress = compute_progress_to_take_profit(side=Side.SELL.value, entry_price=1.105, take_profit=1.101, current_price=1.103)
    assert buy_progress == pytest.approx(0.5)
    assert sell_progress == pytest.approx(0.5)

def test_compute_progress_to_take_profit_clamps_to_unit_interval() -> None:
    progress = compute_progress_to_take_profit(side=Side.BUY.value, entry_price=1.1, take_profit=1.104, current_price=1.11)
    assert progress == pytest.approx(1.0)

def test_compute_progress_to_take_profit_rejects_invalid_side() -> None:
    with pytest.raises(ValidationError, match='side must be BUY or SELL'):
        compute_progress_to_take_profit(side='NONE', entry_price=1.1, take_profit=1.2, current_price=1.15)

def test_evaluate_breakeven_generates_modify_for_buy() -> None:
    position = _buy_position(stop_loss=1.098)
    result = evaluate_breakeven(position=position, current_price=1.102, breakeven_progress_ratio=0.5, digits=5, modify_take_profit=position.take_profit)
    assert result is not None
    assert result.action == OrderAction.MODIFY.value
    assert result.stop_loss == pytest.approx(1.1)
    assert result.take_profit == pytest.approx(1.104)
    assert 'BREAKEVEN' in result.reason

def test_evaluate_breakeven_generates_modify_for_sell() -> None:
    position = _sell_position(stop_loss=1.107)
    result = evaluate_breakeven(position=position, current_price=1.103, breakeven_progress_ratio=0.5, digits=5, modify_take_profit=position.take_profit)
    assert result is not None
    assert result.action == OrderAction.MODIFY.value
    assert result.stop_loss == pytest.approx(1.105)
    assert 'BREAKEVEN' in result.reason

def test_evaluate_breakeven_skips_when_progress_not_reached() -> None:
    position = _buy_position()
    result = evaluate_breakeven(position=position, current_price=1.101, breakeven_progress_ratio=0.5, digits=5, modify_take_profit=position.take_profit)
    assert result is None

def test_evaluate_breakeven_skips_when_stop_loss_already_at_entry() -> None:
    position = _buy_position(stop_loss=1.1)
    result = evaluate_breakeven(position=position, current_price=1.102, breakeven_progress_ratio=0.5, digits=5, modify_take_profit=position.take_profit)
    assert result is None

def test_evaluate_trailing_stop_generates_modify_for_buy() -> None:
    position = _buy_position(stop_loss=1.098)
    result = evaluate_trailing_stop(position=position, current_price=1.103, swing_low=1.101, swing_high=1.104, trailing_buffer=0.0002, digits=5, modify_take_profit=position.take_profit)
    assert result is not None
    assert result.action == OrderAction.MODIFY.value
    assert result.stop_loss == pytest.approx(1.1008)
    assert 'TRAILING' in result.reason

def test_evaluate_trailing_stop_generates_modify_for_sell() -> None:
    position = _sell_position(stop_loss=1.107)
    result = evaluate_trailing_stop(position=position, current_price=1.102, swing_low=1.1, swing_high=1.104, trailing_buffer=0.0002, digits=5, modify_take_profit=position.take_profit)
    assert result is not None
    assert result.action == OrderAction.MODIFY.value
    assert result.stop_loss == pytest.approx(1.1042)
    assert 'TRAILING' in result.reason

def test_evaluate_trailing_stop_uses_price_trail_when_more_aggressive() -> None:
    position = _buy_position(stop_loss=1.098)
    result = evaluate_trailing_stop(position=position, current_price=1.103, swing_low=1.099, swing_high=1.104, trailing_buffer=0.0002, digits=5, modify_take_profit=position.take_profit, price_trail_distance=0.0008)
    assert result is not None
    assert result.stop_loss == pytest.approx(1.1022)
    assert 'TRAILING' in result.reason

def test_evaluate_partial_close_generates_close_with_partial_volume() -> None:
    position = _buy_position(volume=0.1)
    result = evaluate_partial_close(position=position, current_price=1.10304, partial_close_progress_ratio=0.75, partial_close_volume_ratio=0.5, volume_step=0.01)
    assert result is not None
    assert result.action == OrderAction.CLOSE.value
    assert result.volume == pytest.approx(0.05)
    assert 'PARTIAL_CLOSE' in result.reason

def test_evaluate_partial_close_skips_when_already_applied() -> None:
    position = _buy_position(partial_close_applied=True)
    result = evaluate_partial_close(position=position, current_price=1.103, partial_close_progress_ratio=0.75, partial_close_volume_ratio=0.5, volume_step=0.01)
    assert result is None

def test_evaluate_time_stop_generates_close() -> None:
    position = _buy_position(bars_open=120)
    result = evaluate_time_stop(position=position, time_stop_max_bars=120)
    assert result is not None
    assert result.action == OrderAction.CLOSE.value
    assert result.volume == pytest.approx(0.1)
    assert 'TIME_STOP' in result.reason

def test_evaluate_time_stop_skips_before_limit() -> None:
    position = _buy_position(bars_open=10)
    result = evaluate_time_stop(position=position, time_stop_max_bars=120)
    assert result is None

def test_evaluate_trade_management_returns_none_action_without_position() -> None:
    result = evaluate_trade_management(position=None, current_price=1.102, swing_low=1.1, swing_high=1.104, config=_config(), digits=5)
    assert result.action == OrderAction.NONE.value
    assert result.reason == ''

def test_evaluate_trade_management_prioritizes_time_stop_over_modify() -> None:
    position = _buy_position(bars_open=120, stop_loss=1.098)
    result = evaluate_trade_management(position=position, current_price=1.102, swing_low=1.101, swing_high=1.104, config=_config(), digits=5)
    assert result.action == OrderAction.CLOSE.value
    assert 'TIME_STOP' in result.reason

def test_evaluate_trade_management_can_return_breakeven_modify() -> None:
    config = TradeManagementConfig(breakeven_progress_ratio=0.5, trailing_buffer=0.0002, partial_close_progress_ratio=0.95, partial_close_volume_ratio=0.5, time_stop_max_bars=0, volume_step=0.01)
    position = _buy_position(bars_open=5, stop_loss=1.098)
    result = evaluate_trade_management(position=position, current_price=1.102, swing_low=1.097, swing_high=1.104, config=config, digits=5)
    assert result.action == OrderAction.MODIFY.value
    assert 'BREAKEVEN' in result.reason

def test_evaluate_trailing_stop_uses_zero_take_profit_in_trailing_only_mode() -> None:
    position = _buy_position(stop_loss=1.098)
    result = evaluate_trailing_stop(position=position, current_price=1.103, swing_low=1.101, swing_high=1.104, trailing_buffer=0.0002, digits=5, modify_take_profit=0.0)
    assert result is not None
    assert result.take_profit == pytest.approx(0.0)

def test_evaluate_trade_management_can_return_trailing_modify() -> None:
    config = TradeManagementConfig(breakeven_progress_ratio=0.95, trailing_buffer=0.0002, partial_close_progress_ratio=0.95, partial_close_volume_ratio=0.5, time_stop_max_bars=0, volume_step=0.01)
    position = _buy_position(bars_open=5, stop_loss=1.098)
    result = evaluate_trade_management(position=position, current_price=1.103, swing_low=1.101, swing_high=1.104, config=config, digits=5, use_fixed_take_profit=False)
    assert result.action == OrderAction.MODIFY.value
    assert 'TRAILING' in result.reason
    assert result.take_profit == pytest.approx(0.0)


def test_evaluate_trade_management_trails_when_time_stop_gated_by_allow_close() -> None:
    config = TradeManagementConfig(breakeven_progress_ratio=0.95, trailing_buffer=0.0002, partial_close_progress_ratio=0.95, partial_close_volume_ratio=0.5, time_stop_max_bars=30, volume_step=0.01, price_trail_distance=0.0005)
    position = _buy_position(bars_open=60, stop_loss=1.098)
    result = evaluate_trade_management(position=position, current_price=1.106, swing_low=1.102, swing_high=1.108, config=config, digits=5, allow_close=False, use_fixed_take_profit=False)
    assert result.action == OrderAction.MODIFY.value
    assert 'TRAILING' in result.reason

def test_trade_management_never_outputs_buy_or_sell_actions() -> None:
    scenarios: list[TradeManagementResult] = []
    scenarios.append(evaluate_trade_management(position=_buy_position(bars_open=120), current_price=1.102, swing_low=1.101, swing_high=1.104, config=_config(), digits=5))
    scenarios.append(evaluate_trade_management(position=_buy_position(stop_loss=1.098), current_price=1.102, swing_low=1.101, swing_high=1.104, config=TradeManagementConfig(breakeven_progress_ratio=0.5, trailing_buffer=0.0002, partial_close_progress_ratio=0.95, partial_close_volume_ratio=0.5, time_stop_max_bars=0, volume_step=0.01), digits=5))
    scenarios.append(evaluate_trade_management(position=_buy_position(), current_price=1.103, swing_low=1.101, swing_high=1.104, config=TradeManagementConfig(breakeven_progress_ratio=0.95, trailing_buffer=0.0002, partial_close_progress_ratio=0.75, partial_close_volume_ratio=0.5, time_stop_max_bars=0, volume_step=0.01), digits=5))
    for result in scenarios:
        assert result.action in {OrderAction.MODIFY.value, OrderAction.CLOSE.value, OrderAction.NONE.value}
        assert result.action not in {Decision.BUY.value, Decision.SELL.value, OrderAction.OPEN.value}
