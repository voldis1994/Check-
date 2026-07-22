"""BE+0.20 then discrete 3.0-pip trailing acceptance tests."""
from __future__ import annotations
import pytest
from engine.protocol.constants import AckStatus, OrderAction, Side
from engine.protocol.models import AckRecord
from engine.risk.money_step_trailing import (
    REASON_BE_PLUS_NET_PROFIT,
    REASON_PIP_TRAIL_STEP,
    MoneyStepTrailingParams,
    MoneyStepTrailingState,
    choose_protective_sl,
    compute_discrete_pip_trail_sl,
    compute_money_step_sl,
    confirm_protective_sl,
    mark_protective_modify_rejected,
    merge_technical_and_money_step_trailing,
    pip_step_price,
    sl_improves,
)
from engine.risk.trade_management import TradeManagementResult
from engine.state.instance_state import InstanceState
from engine.core.instance import Instance
from engine.execution.engine import apply_ack_to_instance_state
from engine.execution.command import OrderCommand


def _prod_params() -> MoneyStepTrailingParams:
    return MoneyStepTrailingParams(
        enabled=True,
        activation_profit_money=0.50,
        profit_step_money=0.25,
        initial_locked_profit_money=0.20,
        lock_increment_money=0.25,
    )


def _none_technical() -> TradeManagementResult:
    return TradeManagementResult(action=OrderAction.NONE.value, reason='')


def test_01_buy_first_sl_locks_net_0_20() -> None:
    # tick_value=1 per tick_size 0.00001 on 0.01 lot → 1000 money per price unit
    # required_gross=0.20 → distance=0.00020 → SL=1.10020
    sl = compute_money_step_sl(
        side=Side.BUY.value,
        open_price=1.10000,
        locked_profit_money=0.20,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
    )
    assert sl == pytest.approx(1.10020)


def test_02_sell_first_sl_locks_net_0_20() -> None:
    sl = compute_money_step_sl(
        side=Side.SELL.value,
        open_price=1.10000,
        locked_profit_money=0.20,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
    )
    assert sl == pytest.approx(1.09980)


def test_03_commission_included_in_be_plus() -> None:
    # commission=-0.07 (MT4 style) → need +0.27 gross → distance 0.00027
    sl = compute_money_step_sl(
        side=Side.BUY.value,
        open_price=1.10000,
        locked_profit_money=0.20,
        current_swap=0.0,
        current_commission=-0.07,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
    )
    assert sl == pytest.approx(1.10027)


def test_04_negative_swap_included_in_be_plus() -> None:
    sl = compute_money_step_sl(
        side=Side.BUY.value,
        open_price=1.10000,
        locked_profit_money=0.20,
        current_swap=-0.05,
        current_commission=0.0,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
    )
    assert sl == pytest.approx(1.10025)


def test_05_buy_pip_trail_multiple_3_pip_steps() -> None:
    pip = 0.00010
    step = pip_step_price(trailing_step_pips=3.0, pip=pip)
    assert step == pytest.approx(0.00030)
    be_sl = 1.10020
    # Price high enough for three steps: be + 0.00090 = 1.10110, need bid >= 1.10110
    levels = []
    confirmed = be_sl
    for bid in (1.10060, 1.10090, 1.10120, 1.10150):
        nxt = compute_discrete_pip_trail_sl(
            side=Side.BUY.value,
            confirmed_sl=confirmed,
            current_price=bid,
            trailing_step_pips=3.0,
            pip=pip,
            digits=5,
            point=0.00001,
            stop_level=0,
            freeze_level=0,
        )
        if nxt is not None:
            levels.append(nxt)
            confirmed = nxt
    assert levels == [pytest.approx(1.10050), pytest.approx(1.10080), pytest.approx(1.10110), pytest.approx(1.10140)]


def test_06_sell_pip_trail_multiple_3_pip_steps() -> None:
    pip = 0.00010
    be_sl = 1.09980
    confirmed = be_sl
    levels = []
    for ask in (1.09940, 1.09910, 1.09880):
        nxt = compute_discrete_pip_trail_sl(
            side=Side.SELL.value,
            confirmed_sl=confirmed,
            current_price=ask,
            trailing_step_pips=3.0,
            pip=pip,
            digits=5,
            point=0.00001,
            stop_level=0,
            freeze_level=0,
        )
        if nxt is not None:
            levels.append(nxt)
            confirmed = nxt
    assert levels[0] == pytest.approx(1.09950)
    assert levels[1] == pytest.approx(1.09920)
    assert levels[2] == pytest.approx(1.09890)


def test_07_eurusd_5_digit_three_pips_is_0_00030() -> None:
    assert pip_step_price(trailing_step_pips=3.0, pip=0.00010) == pytest.approx(0.00030)
    assert pip_step_price(trailing_step_pips=3.0, pip=0.00010) != pytest.approx(0.00003)


def test_08_jpy_3_digit_pip_conversion() -> None:
    # USDJPY digits=3, point=0.001, pip=0.01 → 3.0 pips = 0.03
    assert pip_step_price(trailing_step_pips=3.0, pip=0.01) == pytest.approx(0.03)
    sl = compute_discrete_pip_trail_sl(
        side=Side.BUY.value,
        confirmed_sl=150.000,
        current_price=150.050,
        trailing_step_pips=3.0,
        pip=0.01,
        digits=3,
        point=0.001,
        stop_level=0,
        freeze_level=0,
    )
    assert sl == pytest.approx(150.030)


def test_09_sl_never_worsens() -> None:
    assert sl_improves(side=Side.BUY.value, current_sl=1.10050, proposed_sl=1.10040, tolerance=1e-5) is False
    assert sl_improves(side=Side.SELL.value, current_sl=1.09950, proposed_sl=1.09960, tolerance=1e-5) is False
    assert choose_protective_sl(side=Side.BUY.value, current_sl=1.10050, technical_sl=1.10040, money_sl=1.10030) == 1.10050


def test_10_rejected_modify_not_confirmed() -> None:
    state = MoneyStepTrailingState(
        peak_net_profit_money=0.60,
        money_trailing_step_index=0,
        locked_profit_money=0.20,
        pending_protective_sl=1.10020,
        pending_trailing_reason=REASON_BE_PLUS_NET_PROFIT,
    )
    rejected = mark_protective_modify_rejected(state, status=AckStatus.REJECTED.value, error_code='130')
    assert rejected.be_plus_confirmed is False
    assert rejected.confirmed_protective_sl is None
    assert rejected.pending_protective_sl == pytest.approx(1.10020)
    assert rejected.last_trailing_broker_error == '130'
    assert rejected.last_trailing_modify_status == AckStatus.REJECTED.value


def test_11_rejected_modify_retries_same_level() -> None:
    state = MoneyStepTrailingState(
        peak_net_profit_money=0.60,
        locked_profit_money=0.20,
        pending_protective_sl=1.10020,
        pending_trailing_reason=REASON_BE_PLUS_NET_PROFIT,
        last_trailing_modify_status=AckStatus.REJECTED.value,
        last_trailing_broker_error='130',
    )
    merge = merge_technical_and_money_step_trailing(
        technical_result=_none_technical(),
        params=_prod_params(),
        state=state,
        side=Side.BUY.value,
        open_price=1.10000,
        current_sl=1.09800,
        current_price=1.10100,
        net_profit_money=0.60,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
        point=0.00001,
        stop_level=0,
        freeze_level=0,
        price_tolerance=0.00001,
        modify_take_profit=0.0,
        sensor_fresh=True,
        trailing_step_pips=3.0,
        pip=0.00010,
    )
    assert merge.management_result.action == OrderAction.MODIFY.value
    assert merge.management_result.stop_loss == pytest.approx(1.10020)
    assert merge.state.pending_protective_sl == pytest.approx(1.10020)
    assert merge.state.be_plus_confirmed is False


def test_12_price_jumps_selects_latest_safe_sl() -> None:
    # From BE 1.10020, bid jumps enough for 3 steps at once → 1.10110
    sl = compute_discrete_pip_trail_sl(
        side=Side.BUY.value,
        confirmed_sl=1.10020,
        current_price=1.10120,
        trailing_step_pips=3.0,
        pip=0.00010,
        digits=5,
        point=0.00001,
        stop_level=0,
        freeze_level=0,
    )
    assert sl == pytest.approx(1.10110)


def test_13_be_plus_does_not_stop_further_trailing() -> None:
    confirmed = MoneyStepTrailingState(
        peak_net_profit_money=0.80,
        money_trailing_step_index=0,
        locked_profit_money=0.20,
        be_plus_confirmed=True,
        confirmed_protective_sl=1.10020,
        last_money_trailing_sl=1.10020,
        computed_be_plus_sl=1.10020,
    )
    merge = merge_technical_and_money_step_trailing(
        technical_result=_none_technical(),
        params=_prod_params(),
        state=confirmed,
        side=Side.BUY.value,
        open_price=1.10000,
        current_sl=1.10020,
        current_price=1.10090,
        net_profit_money=0.80,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
        point=0.00001,
        stop_level=0,
        freeze_level=0,
        price_tolerance=0.00001,
        modify_take_profit=0.0,
        sensor_fresh=True,
        trailing_step_pips=3.0,
        pip=0.00010,
    )
    assert merge.management_result.action == OrderAction.MODIFY.value
    # Bid 1.10090 allows two 3-pip steps from 1.10020 → latest safe 1.10080
    assert merge.management_result.stop_loss == pytest.approx(1.10080)
    assert REASON_PIP_TRAIL_STEP in merge.management_result.reason
    assert merge.state.be_plus_confirmed is True
    # Still pending until ACK
    assert merge.state.confirmed_protective_sl == pytest.approx(1.10020)


def test_14_missing_tick_does_not_invent_be_sl() -> None:
    merge = merge_technical_and_money_step_trailing(
        technical_result=_none_technical(),
        params=_prod_params(),
        state=MoneyStepTrailingState(),
        side=Side.BUY.value,
        open_price=1.10000,
        current_sl=1.09800,
        current_price=1.10100,
        net_profit_money=0.80,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=None,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
        point=0.00001,
        stop_level=0,
        freeze_level=0,
        price_tolerance=0.00001,
        modify_take_profit=0.0,
        sensor_fresh=True,
        trailing_step_pips=3.0,
        pip=0.00010,
    )
    assert merge.skip_reason == 'money_step_trailing_blocked_invalid_tick'
    assert merge.state.be_plus_confirmed is False
    assert merge.state.pending_protective_sl is None


def test_buy_sequential_sl_levels_with_ack_confirmation() -> None:
    """Full BUY path: initial → BE+0.20 → +3pip → +3pip → +3pip."""
    params = _prod_params()
    state = MoneyStepTrailingState()
    # Activate BE
    merge = merge_technical_and_money_step_trailing(
        technical_result=_none_technical(),
        params=params,
        state=state,
        side=Side.BUY.value,
        open_price=1.10000,
        current_sl=1.09800,
        current_price=1.10100,
        net_profit_money=0.55,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
        point=0.00001,
        stop_level=0,
        freeze_level=0,
        price_tolerance=0.00001,
        modify_take_profit=0.0,
        sensor_fresh=True,
        trailing_step_pips=3.0,
        pip=0.00010,
    )
    be_sl = merge.management_result.stop_loss
    assert be_sl == pytest.approx(1.10020)
    assert REASON_BE_PLUS_NET_PROFIT in merge.management_result.reason
    # ACK confirm BE
    state = confirm_protective_sl(
        merge.state,
        broker_sl=float(be_sl),
        price_tolerance=0.00001,
        trailing_step_pips=3.0,
        pip=0.00010,
        digits=5,
        side=Side.BUY.value,
    )
    assert state.be_plus_confirmed is True
    assert state.confirmed_protective_sl == pytest.approx(1.10020)
    assert state.next_pip_trail_sl == pytest.approx(1.10050)
    levels = [1.10020]
    for bid in (1.10060, 1.10090, 1.10120):
        merge = merge_technical_and_money_step_trailing(
            technical_result=_none_technical(),
            params=params,
            state=state,
            side=Side.BUY.value,
            open_price=1.10000,
            current_sl=float(state.confirmed_protective_sl or 0),
            current_price=bid,
            net_profit_money=0.90,
            current_swap=0.0,
            current_commission=0.0,
            tick_value=1.0,
            tick_size=0.00001,
            volume=0.01,
            digits=5,
            point=0.00001,
            stop_level=0,
            freeze_level=0,
            price_tolerance=0.00001,
            modify_take_profit=0.0,
            sensor_fresh=True,
            trailing_step_pips=3.0,
            pip=0.00010,
        )
        assert merge.management_result.action == OrderAction.MODIFY.value
        new_sl = float(merge.management_result.stop_loss)
        levels.append(new_sl)
        state = confirm_protective_sl(
            merge.state,
            broker_sl=new_sl,
            price_tolerance=0.00001,
            trailing_step_pips=3.0,
            pip=0.00010,
            digits=5,
            side=Side.BUY.value,
        )
    assert levels == [pytest.approx(1.10020), pytest.approx(1.10050), pytest.approx(1.10080), pytest.approx(1.10110)]


def test_sell_sequential_sl_levels_with_ack_confirmation() -> None:
    params = _prod_params()
    merge = merge_technical_and_money_step_trailing(
        technical_result=_none_technical(),
        params=params,
        state=MoneyStepTrailingState(),
        side=Side.SELL.value,
        open_price=1.10000,
        current_sl=1.10200,
        current_price=1.09900,
        net_profit_money=0.55,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
        point=0.00001,
        stop_level=0,
        freeze_level=0,
        price_tolerance=0.00001,
        modify_take_profit=0.0,
        sensor_fresh=True,
        trailing_step_pips=3.0,
        pip=0.00010,
    )
    be_sl = float(merge.management_result.stop_loss)
    assert be_sl == pytest.approx(1.09980)
    state = confirm_protective_sl(merge.state, broker_sl=be_sl, price_tolerance=0.00001, trailing_step_pips=3.0, pip=0.00010, digits=5, side=Side.SELL.value)
    levels = [be_sl]
    for ask in (1.09940, 1.09910, 1.09880):
        merge = merge_technical_and_money_step_trailing(
            technical_result=_none_technical(),
            params=params,
            state=state,
            side=Side.SELL.value,
            open_price=1.10000,
            current_sl=float(state.confirmed_protective_sl or 0),
            current_price=ask,
            net_profit_money=0.90,
            current_swap=0.0,
            current_commission=0.0,
            tick_value=1.0,
            tick_size=0.00001,
            volume=0.01,
            digits=5,
            point=0.00001,
            stop_level=0,
            freeze_level=0,
            price_tolerance=0.00001,
            modify_take_profit=0.0,
            sensor_fresh=True,
            trailing_step_pips=3.0,
            pip=0.00010,
        )
        new_sl = float(merge.management_result.stop_loss)
        levels.append(new_sl)
        state = confirm_protective_sl(merge.state, broker_sl=new_sl, price_tolerance=0.00001, trailing_step_pips=3.0, pip=0.00010, digits=5, side=Side.SELL.value)
    assert levels == [pytest.approx(1.09980), pytest.approx(1.09950), pytest.approx(1.09920), pytest.approx(1.09890)]


def test_apply_ack_success_confirms_be_step() -> None:
    instance = Instance(account_id='1', symbol='EURUSD', magic=1)
    state = InstanceState(instance=instance)
    state.update_instrument(digits=5, point=0.00001, pip=0.00010)
    state.update_position(open_ticket=10, position_side=Side.BUY.value, position_volume=0.01, entry_price=1.1, stop_loss=1.098, take_profit=0.0)
    state.pending_protective_sl = 1.10020
    state.pending_trailing_reason = REASON_BE_PLUS_NET_PROFIT
    state.locked_profit_money = 0.20
    cmd = OrderCommand(command_id='c1', action=OrderAction.MODIFY.value, side=Side.BUY.value, stop_loss=1.10020, take_profit=0.0, ticket=10, reason='BE', decision_id='d1')
    ack = AckRecord(schema_version='1.0.0', timestamp_utc='2026-07-22T10:00:00.000Z', command_id='c1', account_id='1', symbol='EURUSD', magic=1, status=AckStatus.SUCCESS.value, ticket=10)
    apply_ack_to_instance_state(state, cmd, ack)
    assert state.be_plus_confirmed is True
    assert state.confirmed_protective_sl == pytest.approx(1.10020)
    assert state.pending_protective_sl is None
    assert state.last_trailing_modify_status == 'SUCCESS'


def test_apply_ack_reject_keeps_pending() -> None:
    instance = Instance(account_id='1', symbol='EURUSD', magic=1)
    state = InstanceState(instance=instance)
    state.update_instrument(digits=5, point=0.00001, pip=0.00010)
    state.update_position(open_ticket=10, position_side=Side.BUY.value, position_volume=0.01, entry_price=1.1, stop_loss=1.098, take_profit=0.0)
    state.pending_protective_sl = 1.10020
    state.pending_trailing_reason = REASON_BE_PLUS_NET_PROFIT
    cmd = OrderCommand(command_id='c2', action=OrderAction.MODIFY.value, side=Side.BUY.value, stop_loss=1.10020, take_profit=0.0, ticket=10, reason='BE', decision_id='d2')
    ack = AckRecord(schema_version='1.0.0', timestamp_utc='2026-07-22T10:00:00.000Z', command_id='c2', account_id='1', symbol='EURUSD', magic=1, status=AckStatus.REJECTED.value, ticket=10, error_code=130, error_message='invalid stops')
    apply_ack_to_instance_state(state, cmd, ack)
    assert state.be_plus_confirmed is False
    assert state.pending_protective_sl == pytest.approx(1.10020)
    assert state.last_trailing_broker_error == '130'
