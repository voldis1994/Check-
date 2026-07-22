"""Market snapshot loader/validator — universal MT4 instruments via tick/point."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from checktrader.domain.errors import DataError
from checktrader.domain.market import Candle, TickQuote
from checktrader.domain.money import SymbolSpecs, spread_points, spread_price, spread_ticks
from checktrader.observability.reason_codes import ReasonCode


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    protocol_version: str
    sequence: int
    generated_at_utc: str
    account_number: str
    server: str
    specs: SymbolSpecs
    bid: float
    ask: float
    spread_price: float
    spread_points: float
    spread_ticks: float
    trade_allowed: bool
    market_open: bool
    bars_m1: tuple[Candle, ...]

    @property
    def spread_pips(self) -> float:
        """Legacy alias — prefer spread_price / spread_ticks for decisions."""
        if self.specs.pip_size > 0:
            return self.spread_price / self.specs.pip_size
        return 0.0


def _candle(payload: dict[str, Any], timeframe: str) -> Candle:
    return Candle(
        open_time_utc=str(payload["open_time_utc"]),
        close_time_utc=str(payload["close_time_utc"]),
        open=float(payload["open"]),
        high=float(payload["high"]),
        low=float(payload["low"]),
        close=float(payload["close"]),
        tick_volume=float(payload.get("tick_volume", 0)),
        spread=float(payload.get("spread", 0)),
        complete=bool(payload.get("complete", True)),
        timeframe=timeframe,
    )


def parse_market_snapshot(payload: dict[str, Any]) -> MarketSnapshot:
    required = (
        "protocol_version",
        "sequence",
        "generated_at_utc",
        "account_number",
        "symbol",
        "digits",
        "point",
        "bid",
        "ask",
        "tick_size",
        "tick_value",
        "minimum_lot",
        "maximum_lot",
        "lot_step",
        "bars_m1",
    )
    for key in required:
        if key not in payload:
            raise DataError(f"market missing {key}", reason=ReasonCode.DATA_MISSING, context={"field": key})

    tick_size = float(payload["tick_size"])
    point = float(payload["point"])
    if tick_size <= 0:
        tick_size = point
    if tick_size <= 0:
        raise DataError("invalid tick_size/point", reason=ReasonCode.SYMBOL_SPEC_MISSING)

    # pip_size is optional legacy; default to tick_size (never invent Forex ×10).
    pip_size = float(payload["pip_size"]) if payload.get("pip_size") not in (None, "") else tick_size
    if pip_size <= 0:
        pip_size = tick_size

    specs = SymbolSpecs(
        symbol=str(payload["symbol"]),
        digits=int(payload["digits"]),
        point=point,
        tick_size=tick_size,
        tick_value=float(payload["tick_value"]),
        minimum_lot=float(payload["minimum_lot"]),
        maximum_lot=float(payload["maximum_lot"]),
        lot_step=float(payload["lot_step"]),
        stop_level_points=int(payload.get("stop_level_points", 0)),
        freeze_level_points=int(payload.get("freeze_level_points", 0)),
        pip_size=pip_size,
    )
    if specs.tick_value <= 0 or specs.digits < 0 or specs.point <= 0:
        raise DataError("invalid symbol metadata", reason=ReasonCode.SYMBOL_SPEC_MISSING)

    bid = float(payload["bid"])
    ask = float(payload["ask"])
    if bid <= 0 or ask <= 0 or ask < bid:
        raise DataError("invalid bid/ask", reason=ReasonCode.DATA_INVALID)

    spr_price = spread_price(bid=bid, ask=ask)
    spr_points = float(payload.get("spread_points") or spread_points(bid=bid, ask=ask, point=specs.point))
    spr_ticks = float(payload.get("spread_ticks") or spread_ticks(bid=bid, ask=ask, tick_size=specs.tick_size))

    bars = tuple(_candle(item, "M1") for item in payload["bars_m1"])
    return MarketSnapshot(
        protocol_version=str(payload["protocol_version"]),
        sequence=int(payload["sequence"]),
        generated_at_utc=str(payload["generated_at_utc"]),
        account_number=str(payload["account_number"]),
        server=str(payload.get("server", "")),
        specs=specs,
        bid=bid,
        ask=ask,
        spread_price=spr_price,
        spread_points=spr_points,
        spread_ticks=spr_ticks,
        trade_allowed=bool(payload.get("trade_allowed", True)),
        market_open=bool(payload.get("market_open", True)),
        bars_m1=bars,
    )


def tick_from_market(snapshot: MarketSnapshot) -> TickQuote:
    return TickQuote(
        bid=snapshot.bid,
        ask=snapshot.ask,
        time_utc=snapshot.generated_at_utc,
        spread_price=snapshot.spread_price,
        spread_points=snapshot.spread_points,
        spread_ticks=snapshot.spread_ticks,
    )
