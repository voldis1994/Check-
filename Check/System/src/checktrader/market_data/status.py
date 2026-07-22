"""Status snapshot parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from checktrader.domain.enums import Side
from checktrader.domain.errors import DataError
from checktrader.domain.money import compute_net_profit
from checktrader.domain.orders import BrokerPosition
from checktrader.observability.reason_codes import ReasonCode


@dataclass(frozen=True, slots=True)
class StatusSnapshot:
    protocol_version: str
    sequence: int
    generated_at_utc: str
    account_number: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    trade_allowed: bool
    expert_enabled: bool
    positions: tuple[BrokerPosition, ...]


def parse_status_snapshot(payload: dict[str, Any]) -> StatusSnapshot:
    for key in ("protocol_version", "sequence", "generated_at_utc", "account_number", "balance", "equity"):
        if key not in payload:
            raise DataError(f"status missing {key}", reason=ReasonCode.DATA_MISSING, context={"field": key})
    positions: list[BrokerPosition] = []
    raw_positions = payload.get("positions", payload.get("open_positions", []))
    for item in raw_positions:
        profit = float(item.get("profit", 0))
        swap = float(item.get("swap", 0))
        commission = float(item.get("commission", 0))
        positions.append(
            BrokerPosition(
                ticket=int(item["ticket"]),
                symbol=str(item["symbol"]),
                magic=int(item["magic"]),
                side=Side(str(item["side"])),
                volume=float(item["volume"]),
                open_time_utc=str(item.get("open_time", item.get("open_time_utc", ""))),
                open_price=float(item.get("open_price", 0)),
                stop_loss=float(item.get("stop_loss", 0)),
                take_profit=float(item.get("take_profit", 0)),
                current_price=float(item.get("current_price", 0)),
                profit=profit,
                swap=swap,
                commission=commission,
                net_profit=float(
                    item.get("net_profit", compute_net_profit(profit=profit, swap=swap, commission=commission))
                ),
                comment=str(item.get("comment", "")),
            )
        )
    return StatusSnapshot(
        protocol_version=str(payload["protocol_version"]),
        sequence=int(payload["sequence"]),
        generated_at_utc=str(payload["generated_at_utc"]),
        account_number=str(payload["account_number"]),
        balance=float(payload["balance"]),
        equity=float(payload["equity"]),
        margin=float(payload.get("margin", 0)),
        free_margin=float(payload.get("free_margin", payload.get("margin_free", 0))),
        margin_level=float(payload.get("margin_level", 0)),
        trade_allowed=bool(payload.get("trade_allowed", True)),
        expert_enabled=bool(payload.get("expert_enabled", True)),
        positions=tuple(positions),
    )
