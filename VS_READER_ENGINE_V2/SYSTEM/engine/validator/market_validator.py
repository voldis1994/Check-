from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO

from engine.protocol.constants import MARKET_CSV_COLUMNS, TIMEFRAME_M1, ValidationStatus


@dataclass(frozen=True)
class ValidationResult:
    status: str
    errors: tuple[str, ...]
    row_count: int

    @property
    def is_valid(self) -> bool:
        return self.status == ValidationStatus.VALID.value


def _parse_float(raw: str, field: str, row: int, errors: list[str]) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        errors.append(f"row {row}: invalid number in {field}")
        return None


def _parse_int(raw: str, field: str, row: int, errors: list[str]) -> int | None:
    try:
        if "." in raw:
            raise ValueError("integer expected")
        return int(raw)
    except (TypeError, ValueError):
        errors.append(f"row {row}: invalid integer in {field}")
        return None


def validate_market_csv(raw_text: str) -> ValidationResult:
    errors: list[str] = []
    if not isinstance(raw_text, str) or not raw_text.strip():
        return ValidationResult(
            status=ValidationStatus.INVALID.value,
            errors=("market csv is empty",),
            row_count=0,
        )

    reader = csv.DictReader(StringIO(raw_text.strip()))
    row_count = 0
    if reader.fieldnames is None or tuple(reader.fieldnames) != MARKET_CSV_COLUMNS:
        errors.append("missing or invalid market csv columns")
        return ValidationResult(
            status=ValidationStatus.INVALID.value,
            errors=tuple(errors),
            row_count=0,
        )

    last_time_utc: str | None = None
    seen_times: set[str] = set()
    for row_index, row in enumerate(reader, start=2):
        if row is None or not any(value not in (None, "") for value in row.values()):
            continue
        row_count += 1
        time_utc = row["time_utc"]
        if not isinstance(time_utc, str) or not time_utc.strip():
            errors.append(f"row {row_index}: missing time_utc")
            continue
        if time_utc in seen_times:
            errors.append(f"row {row_index}: duplicate time_utc")
        if last_time_utc is not None and time_utc <= last_time_utc:
            errors.append(f"row {row_index}: time_utc is not strictly increasing")
        seen_times.add(time_utc)
        last_time_utc = time_utc

        timeframe = row["timeframe"]
        if timeframe != TIMEFRAME_M1:
            errors.append(f"row {row_index}: timeframe must be {TIMEFRAME_M1}")

        open_price = _parse_float(row["open"], "open", row_index, errors)
        high_price = _parse_float(row["high"], "high", row_index, errors)
        low_price = _parse_float(row["low"], "low", row_index, errors)
        close_price = _parse_float(row["close"], "close", row_index, errors)
        point = _parse_float(row["point"], "point", row_index, errors)
        digits = _parse_int(row["digits"], "digits", row_index, errors)

        if digits is not None and digits <= 0:
            errors.append(f"row {row_index}: digits must be positive")
        if point is not None and point <= 0:
            errors.append(f"row {row_index}: point must be positive")

        prices = [open_price, high_price, low_price, close_price]
        if all(price is not None for price in prices):
            open_price_v = float(open_price)
            high_price_v = float(high_price)
            low_price_v = float(low_price)
            close_price_v = float(close_price)
            if min(open_price_v, high_price_v, low_price_v, close_price_v) <= 0:
                errors.append(f"row {row_index}: prices must be positive")
            if high_price_v < max(open_price_v, close_price_v, low_price_v):
                errors.append(f"row {row_index}: high must be >= max(open, close, low)")
            if low_price_v > min(open_price_v, close_price_v, high_price_v):
                errors.append(f"row {row_index}: low must be <= min(open, close, high)")

    status = ValidationStatus.VALID.value if not errors else ValidationStatus.INVALID.value
    return ValidationResult(status=status, errors=tuple(errors), row_count=row_count)
