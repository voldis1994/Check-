from __future__ import annotations

import csv
import math
from io import StringIO

from engine.protocol.constants import FLOAT_TOLERANCE, SENSOR_CSV_COLUMNS, ValidationStatus
from engine.validator.market_validator import ValidationResult


def _parse_float(raw: str, field: str, row: int, errors: list[str]) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        errors.append(f"row {row}: invalid number in {field}")
        return None


def validate_sensor_csv(raw_text: str) -> ValidationResult:
    errors: list[str] = []
    if not isinstance(raw_text, str) or not raw_text.strip():
        return ValidationResult(
            status=ValidationStatus.INVALID.value,
            errors=("sensor csv is empty",),
            row_count=0,
        )

    reader = csv.DictReader(StringIO(raw_text.strip()))
    row_count = 0
    if reader.fieldnames is None or tuple(reader.fieldnames) != SENSOR_CSV_COLUMNS:
        return ValidationResult(
            status=ValidationStatus.INVALID.value,
            errors=("missing or invalid sensor csv columns",),
            row_count=0,
        )

    for row_index, row in enumerate(reader, start=2):
        if row is None or not any(value not in (None, "") for value in row.values()):
            continue
        row_count += 1
        bid = _parse_float(row["bid"], "bid", row_index, errors)
        ask = _parse_float(row["ask"], "ask", row_index, errors)
        spread = _parse_float(row["spread"], "spread", row_index, errors)
        spread_points = _parse_float(row["spread_points"], "spread_points", row_index, errors)
        point = _parse_float(row["point"], "point", row_index, errors)

        if point is not None and point <= 0:
            errors.append(f"row {row_index}: point must be positive")

        if bid is not None and ask is not None:
            if ask < bid:
                errors.append(f"row {row_index}: ask must be >= bid")
            if spread is not None:
                expected_spread = ask - bid
                if not math.isclose(spread, expected_spread, rel_tol=0.0, abs_tol=FLOAT_TOLERANCE):
                    errors.append(f"row {row_index}: spread must equal ask - bid")
                if spread < 0:
                    errors.append(f"row {row_index}: spread must be non-negative")
            if spread is not None and spread_points is not None and point is not None and point > 0:
                expected_spread_points = spread / point
                if not math.isclose(
                    spread_points,
                    expected_spread_points,
                    rel_tol=0.0,
                    abs_tol=FLOAT_TOLERANCE,
                ):
                    errors.append(f"row {row_index}: spread_points must equal spread / point")

    status = ValidationStatus.VALID.value if not errors else ValidationStatus.INVALID.value
    return ValidationResult(status=status, errors=tuple(errors), row_count=row_count)
