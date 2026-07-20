from __future__ import annotations
import csv
import math
from dataclasses import dataclass
from io import StringIO
from engine.protocol.constants import FLOAT_TOLERANCE, SENSOR_CSV_COLUMNS, ValidationStatus
from engine.validator.market_validator import ValidationResult

# Sensor ticks arrive ~500ms; keep a bounded newest window for live reads.
DEFAULT_SENSOR_SANITIZE_MAX_ROWS = 2000

@dataclass(frozen=True)
class SensorCsvSanitizeResult:
    raw_text: str
    changed: bool
    dropped_duplicates: int
    reordered: bool
    truncated: bool
    row_count: int

def _parse_float(raw: str, field: str, row: int, errors: list[str]) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        errors.append(f'row {row}: invalid number in {field}')
        return None

def sanitize_sensor_csv(raw_text: str, *, max_rows: int = DEFAULT_SENSOR_SANITIZE_MAX_ROWS) -> SensorCsvSanitizeResult:
    """Deduplicate by time_utc (keep last), sort ascending, truncate to newest rows."""
    if not isinstance(raw_text, str) or not raw_text.strip():
        return SensorCsvSanitizeResult(raw_text=raw_text if isinstance(raw_text, str) else '', changed=False, dropped_duplicates=0, reordered=False, truncated=False, row_count=0)
    reader = csv.DictReader(StringIO(raw_text.strip()))
    if reader.fieldnames is None or tuple(reader.fieldnames) != SENSOR_CSV_COLUMNS:
        return SensorCsvSanitizeResult(raw_text=raw_text, changed=False, dropped_duplicates=0, reordered=False, truncated=False, row_count=0)
    rows_by_time: dict[str, dict[str, str]] = {}
    order_before: list[str] = []
    dropped_duplicates = 0
    for row in reader:
        if row is None or not any((value not in (None, '') for value in row.values())):
            continue
        time_utc = row.get('time_utc')
        if not isinstance(time_utc, str) or not time_utc.strip():
            continue
        if time_utc in rows_by_time:
            dropped_duplicates += 1
        else:
            order_before.append(time_utc)
        rows_by_time[time_utc] = {column: (row.get(column) or '') for column in SENSOR_CSV_COLUMNS}
    if not rows_by_time:
        return SensorCsvSanitizeResult(raw_text=raw_text, changed=False, dropped_duplicates=0, reordered=False, truncated=False, row_count=0)
    sorted_times = sorted(rows_by_time.keys())
    reordered = sorted_times != order_before
    truncated = False
    if max_rows > 0 and len(sorted_times) > max_rows:
        sorted_times = sorted_times[-max_rows:]
        truncated = True
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=list(SENSOR_CSV_COLUMNS), lineterminator='\n')
    writer.writeheader()
    for time_utc in sorted_times:
        writer.writerow(rows_by_time[time_utc])
    cleaned = output.getvalue()
    changed = dropped_duplicates > 0 or reordered or truncated
    if changed:
        if not cleaned.endswith('\n'):
            cleaned += '\n'
    else:
        cleaned = raw_text
    return SensorCsvSanitizeResult(
        raw_text=cleaned,
        changed=changed,
        dropped_duplicates=dropped_duplicates,
        reordered=reordered,
        truncated=truncated,
        row_count=len(sorted_times),
    )

def validate_sensor_csv(raw_text: str) -> ValidationResult:
    errors: list[str] = []
    if not isinstance(raw_text, str) or not raw_text.strip():
        return ValidationResult(status=ValidationStatus.INVALID.value, errors=('sensor csv is empty',), row_count=0)
    reader = csv.DictReader(StringIO(raw_text.strip()))
    row_count = 0
    if reader.fieldnames is None or tuple(reader.fieldnames) != SENSOR_CSV_COLUMNS:
        return ValidationResult(status=ValidationStatus.INVALID.value, errors=('missing or invalid sensor csv columns',), row_count=0)
    for row_index, row in enumerate(reader, start=2):
        if row is None or not any((value not in (None, '') for value in row.values())):
            continue
        row_count += 1
        bid = _parse_float(row['bid'], 'bid', row_index, errors)
        ask = _parse_float(row['ask'], 'ask', row_index, errors)
        spread = _parse_float(row['spread'], 'spread', row_index, errors)
        spread_points = _parse_float(row['spread_points'], 'spread_points', row_index, errors)
        point = _parse_float(row['point'], 'point', row_index, errors)
        if point is not None and point <= 0:
            errors.append(f'row {row_index}: point must be positive')
        if bid is not None and ask is not None:
            if ask < bid:
                errors.append(f'row {row_index}: ask must be >= bid')
            if spread is not None:
                expected_spread = ask - bid
                if not math.isclose(spread, expected_spread, rel_tol=0.0, abs_tol=FLOAT_TOLERANCE):
                    errors.append(f'row {row_index}: spread must equal ask - bid')
                if spread < 0:
                    errors.append(f'row {row_index}: spread must be non-negative')
            if spread is not None and spread_points is not None and (point is not None) and (point > 0):
                expected_spread_points = spread / point
                if not math.isclose(spread_points, expected_spread_points, rel_tol=0.0, abs_tol=FLOAT_TOLERANCE):
                    errors.append(f'row {row_index}: spread_points must equal spread / point')
    status = ValidationStatus.VALID.value if not errors else ValidationStatus.INVALID.value
    return ValidationResult(status=status, errors=tuple(errors), row_count=row_count)
