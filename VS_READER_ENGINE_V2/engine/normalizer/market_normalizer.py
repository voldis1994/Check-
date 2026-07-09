from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from engine.protocol.errors import ValidationError
from engine.protocol.parser import parse_market_csv
from engine.validator.market_validator import validate_market_csv


@dataclass(frozen=True)
class NormalizedMarketBar:
    time_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str
    timeframe: str
    digits: int
    point: float
    bar_index: int


def _parse_utc_timestamp(value: str) -> datetime:
    iso_value = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(iso_value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_market_csv(raw_text: str) -> tuple[NormalizedMarketBar, ...]:
    validation = validate_market_csv(raw_text)
    if not validation.is_valid:
        raise ValidationError(
            "market csv validation failed",
            module="normalizer.market_normalizer",
            context={"errors": validation.errors},
        )

    parsed_bars = parse_market_csv(raw_text)
    normalized: list[NormalizedMarketBar] = []
    for index, bar in enumerate(parsed_bars):
        normalized.append(
            NormalizedMarketBar(
                time_utc=_parse_utc_timestamp(bar.time_utc),
                open=round(bar.open, bar.digits),
                high=round(bar.high, bar.digits),
                low=round(bar.low, bar.digits),
                close=round(bar.close, bar.digits),
                volume=bar.volume,
                symbol=bar.symbol,
                timeframe=bar.timeframe,
                digits=bar.digits,
                point=bar.point,
                bar_index=index,
            )
        )
    return tuple(normalized)
