"""Shared helpers for SYSTEM v2 tests — import explicitly (shared across v2 test packages)."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from checktrader.config.loader import load_system_config
from checktrader.config.models import SystemConfig
from checktrader.domain.enums import OrderAction, Side
from checktrader.domain.execution import PendingCommandState
from checktrader.domain.money import SymbolSpecs
from checktrader.domain.orders import BrokerPosition
from checktrader.market_data.loader import MarketSnapshot, parse_market_snapshot
from checktrader.market_data.status import StatusSnapshot, parse_status_snapshot

FIXTURES_DIR = Path(__file__).resolve().parent
SYSTEM_TEST_CONFIG = FIXTURES_DIR / "system_test.json"

EURUSD_SPECS = SymbolSpecs(
    symbol="EURUSD",
    digits=5,
    point=0.00001,
    pip_size=0.0001,
    tick_size=0.00001,
    tick_value=1.0,
    minimum_lot=0.01,
    maximum_lot=100.0,
    lot_step=0.01,
    stop_level_points=0,
    freeze_level_points=0,
)


def load_test_config(**overrides: Any) -> SystemConfig:
    payload = json.loads(SYSTEM_TEST_CONFIG.read_text(encoding="utf-8"))
    _deep_update(payload, overrides)
    # Bypass file round-trip for overrides: validate via model + live checks
    from checktrader.config.models import SystemConfig as SC
    from checktrader.config.validator import validate_live_config

    config = SC.model_validate(payload)
    validate_live_config(config, require_live_accounts=True)
    return config


def load_test_config_from_file() -> SystemConfig:
    return load_system_config(SYSTEM_TEST_CONFIG, require_live_accounts=True)


def _deep_update(base: dict[str, Any], overrides: dict[str, Any]) -> None:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value


def eurusd_market_payload(
    *,
    bars_m1: list[dict[str, Any]],
    generated_at_utc: str = "2026-03-01T12:00:00Z",
    bid: float = 1.10000,
    ask: float = 1.10020,
    sequence: int = 1,
    account_number: str = "999",
    tick_value: float = 1.0,
    tick_size: float = 0.00001,
) -> dict[str, Any]:
    return {
        "protocol_version": "2.0.0",
        "sequence": sequence,
        "generated_at_utc": generated_at_utc,
        "account_number": account_number,
        "server": "Demo-Server",
        "symbol": "EURUSD",
        "digits": 5,
        "point": 0.00001,
        "pip_size": 0.0001,
        "bid": bid,
        "ask": ask,
        "spread_points": round((ask - bid) / 0.00001),
        "spread_pips": round((ask - bid) / 0.0001, 2),
        "tick_size": tick_size,
        "tick_value": tick_value,
        "minimum_lot": 0.01,
        "maximum_lot": 100.0,
        "lot_step": 0.01,
        "stop_level_points": 0,
        "freeze_level_points": 0,
        "trade_allowed": True,
        "market_open": True,
        "bars_m1": bars_m1,
    }


def make_market_snapshot(**kwargs: Any) -> MarketSnapshot:
    return parse_market_snapshot(eurusd_market_payload(**kwargs))


def make_status_snapshot(
    *,
    generated_at_utc: str = "2026-03-01T12:00:00Z",
    account_number: str = "999",
    balance: float = 10_000.0,
    equity: float = 10_000.0,
    free_margin: float = 9_000.0,
    margin: float = 1_000.0,
    positions: list[dict[str, Any]] | None = None,
    trade_allowed: bool = True,
    expert_enabled: bool = True,
    sequence: int = 1,
) -> StatusSnapshot:
    payload = {
        "protocol_version": "2.0.0",
        "sequence": sequence,
        "generated_at_utc": generated_at_utc,
        "account_number": account_number,
        "server": "Demo-Server",
        "balance": balance,
        "equity": equity,
        "margin": margin,
        "free_margin": free_margin,
        "margin_level": 1000.0,
        "trade_allowed": trade_allowed,
        "expert_enabled": expert_enabled,
        "open_positions": positions or [],
    }
    return parse_status_snapshot(payload)


def broker_position(
    *,
    ticket: int = 1001,
    side: Side = Side.BUY,
    volume: float = 0.01,
    open_price: float = 1.10000,
    stop_loss: float = 1.09800,
    take_profit: float = 1.10300,
    current_price: float = 1.10050,
    profit: float = 0.5,
    swap: float = 0.0,
    commission: float = 0.0,
    net_profit: float | None = None,
    magic: int = 19942026,
    symbol: str = "EURUSD",
    open_time_utc: str = "2026-03-01T11:00:00Z",
) -> BrokerPosition:
    net = profit + swap + commission if net_profit is None else net_profit
    return BrokerPosition(
        ticket=ticket,
        symbol=symbol,
        magic=magic,
        side=side,
        volume=volume,
        open_time_utc=open_time_utc,
        open_price=open_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        current_price=current_price,
        profit=profit,
        swap=swap,
        commission=commission,
        net_profit=net,
    )


def broker_position_payload(pos: BrokerPosition) -> dict[str, Any]:
    return {
        "ticket": pos.ticket,
        "symbol": pos.symbol,
        "magic": pos.magic,
        "side": pos.side.value,
        "volume": pos.volume,
        "open_time_utc": pos.open_time_utc,
        "open_price": pos.open_price,
        "stop_loss": pos.stop_loss,
        "take_profit": pos.take_profit,
        "current_price": pos.current_price,
        "profit": pos.profit,
        "swap": pos.swap,
        "commission": pos.commission,
        "net_profit": pos.net_profit,
    }


def prepare_bridge(root: Path) -> Path:
    bridge = root / "runtime" / "bridge"
    for name in ("market", "status", "commands", "acknowledgements", "archive"):
        (bridge / name).mkdir(parents=True, exist_ok=True)
    (root / "runtime" / "state").mkdir(parents=True, exist_ok=True)
    (root / "runtime" / "logs").mkdir(parents=True, exist_ok=True)
    return bridge


def config_for_tmp(root: Path, **overrides: Any) -> SystemConfig:
    merged = {
        "paths": {
            "root": str(root),
            "bridge": "runtime/bridge",
            "state": "runtime/state",
            "logs": "runtime/logs",
        }
    }
    merged = deepcopy(merged)
    _deep_update(merged, overrides)
    return load_test_config(**merged)


def make_pending(
    *,
    command_id: str,
    action: str = "OPEN",
    account_number: str = "999",
    server: str = "Demo-Server",
    instance_id: str = "EURUSD_M1_PRIMARY",
    symbol: str = "EURUSD",
    magic: int = 19942026,
    ticket: int | None = None,
    requested_stop_loss: float | None = None,
    requested_volume: float | None = 0.01,
    requested_price: float | None = None,
    setup_fingerprint: str | None = None,
    created_at: str = "2026-03-01T12:00:00Z",
    last_attempt_at: str | None = None,
    acknowledgement_deadline: str = "2026-03-01T12:00:05Z",
    retry_count: int = 0,
    maximum_retries: int = 3,
) -> PendingCommandState:
    return PendingCommandState(
        command_id=command_id,
        action=OrderAction(action),
        account_number=account_number,
        server=server,
        instance_id=instance_id,
        symbol=symbol,
        magic=magic,
        ticket=ticket,
        setup_fingerprint=setup_fingerprint,
        requested_price=requested_price,
        requested_volume=requested_volume,
        requested_stop_loss=requested_stop_loss,
        created_at=created_at,
        last_attempt_at=last_attempt_at or created_at,
        retry_count=retry_count,
        maximum_retries=maximum_retries,
        acknowledgement_deadline=acknowledgement_deadline,
    )
