"""Market data validation — re-exports + snapshot checks."""

from __future__ import annotations

from checktrader.domain.errors import DataError
from checktrader.market_data.aggregator import validate_candle_sequence
from checktrader.market_data.loader import MarketSnapshot
from checktrader.observability.reason_codes import ReasonCode


def validate_market_snapshot(snapshot: MarketSnapshot) -> None:
    if snapshot.specs.tick_size <= 0 or snapshot.specs.tick_value <= 0:
        raise DataError("invalid tick specs", reason=ReasonCode.SYMBOL_SPEC_MISSING)
    if snapshot.bid <= 0 or snapshot.ask <= 0 or snapshot.ask < snapshot.bid:
        raise DataError("invalid bid/ask", reason=ReasonCode.DATA_INVALID)
    validate_candle_sequence(list(snapshot.bars_m1))


__all__ = ["validate_candle_sequence", "validate_market_snapshot"]
