from __future__ import annotations
import csv
from dataclasses import dataclass
from io import StringIO
from engine.protocol.constants import MARKET_CSV_COLUMNS, TIMEFRAME_M1, ValidationStatus

# Keep enough history for analysis lookback while bounding corrupt giant files.
DEFAULT_MARKET_SANITIZE_MAX_ROWS = 5000

@dataclass(frozen=True)
class ValidationResult:
    status: str
    errors: tuple[str, ...]
    row_count: int

    @property
    def is_valid(self) -> bool:
        return self.status == ValidationStatus.VALID.value

@dataclass(frozen=True)
class MarketCsvSanitizeResult:
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

def _parse_int(raw: str, field: str, row: int, errors: list[str]) -> int | None:
    try:
        if '.' in raw:
            raise ValueError('integer expected')
        return int(raw)
    except (TypeError, ValueError):
        errors.append(f'row {row}: invalid integer in {field}')
        return None

def sanitize_market_csv(raw_text: str, *, max_rows: int = DEFAULT_MARKET_SANITIZE_MAX_ROWS) -> MarketCsvSanitizeResult:
    """Deduplicate by time_utc (keep last), sort ascending, optionally truncate to newest rows.

    Repairs live market CSVs that MT4 append/dedupe left non-monotonic so cycles stop SKIP-ing.
    """
    if not isinstance(raw_text, str) or not raw_text.strip():
        return MarketCsvSanitizeResult(raw_text=raw_text if isinstance(raw_text, str) else '', changed=False, dropped_duplicates=0, reordered=False, truncated=False, row_count=0)
    reader = csv.DictReader(StringIO(raw_text.strip()))
    if reader.fieldnames is None or tuple(reader.fieldnames) != MARKET_CSV_COLUMNS:
        return MarketCsvSanitizeResult(raw_text=raw_text, changed=False, dropped_duplicates=0, reordered=False, truncated=False, row_count=0)
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
        # Keep last occurrence for each timestamp.
        rows_by_time[time_utc] = {column: (row.get(column) or '') for column in MARKET_CSV_COLUMNS}
    if not rows_by_time:
        return MarketCsvSanitizeResult(raw_text=raw_text, changed=False, dropped_duplicates=0, reordered=False, truncated=False, row_count=0)
    sorted_times = sorted(rows_by_time.keys())
    reordered = sorted_times != order_before
    truncated = False
    if max_rows > 0 and len(sorted_times) > max_rows:
        sorted_times = sorted_times[-max_rows:]
        truncated = True
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=list(MARKET_CSV_COLUMNS), lineterminator='\n')
    writer.writeheader()
    for time_utc in sorted_times:
        writer.writerow(rows_by_time[time_utc])
    cleaned = output.getvalue()
    changed = dropped_duplicates > 0 or reordered or truncated
    if changed:
        # Preserve final newline for MT4 append compatibility.
        if not cleaned.endswith('\n'):
            cleaned += '\n'
    else:
        cleaned = raw_text
    return MarketCsvSanitizeResult(
        raw_text=cleaned,
        changed=changed,
        dropped_duplicates=dropped_duplicates,
        reordered=reordered,
        truncated=truncated,
        row_count=len(sorted_times),
    )

def validate_market_csv(raw_text: str) -> ValidationResult:
    errors: list[str] = []
    if not isinstance(raw_text, str) or not raw_text.strip():
        return ValidationResult(status=ValidationStatus.INVALID.value, errors=('market csv is empty',), row_count=0)
    reader = csv.DictReader(StringIO(raw_text.strip()))
    row_count = 0
    if reader.fieldnames is None or tuple(reader.fieldnames) != MARKET_CSV_COLUMNS:
        errors.append('missing or invalid market csv columns')
        return ValidationResult(status=ValidationStatus.INVALID.value, errors=tuple(errors), row_count=0)
    last_time_utc: str | None = None
    seen_times: set[str] = set()
    for row_index, row in enumerate(reader, start=2):
        if row is None or not any((value not in (None, '') for value in row.values())):
            continue
        row_count += 1
        time_utc = row['time_utc']
        if not isinstance(time_utc, str) or not time_utc.strip():
            errors.append(f'row {row_index}: missing time_utc')
            continue
        if time_utc in seen_times:
            errors.append(f'row {row_index}: duplicate time_utc')
        if last_time_utc is not None and time_utc <= last_time_utc:
            errors.append(f'row {row_index}: time_utc is not strictly increasing')
        seen_times.add(time_utc)
        last_time_utc = time_utc
        timeframe = row['timeframe']
        if timeframe != TIMEFRAME_M1:
            errors.append(f'row {row_index}: timeframe must be {TIMEFRAME_M1}')
        open_price = _parse_float(row['open'], 'open', row_index, errors)
        high_price = _parse_float(row['high'], 'high', row_index, errors)
        low_price = _parse_float(row['low'], 'low', row_index, errors)
        close_price = _parse_float(row['close'], 'close', row_index, errors)
        point = _parse_float(row['point'], 'point', row_index, errors)
        digits = _parse_int(row['digits'], 'digits', row_index, errors)
        if digits is not None and digits <= 0:
            errors.append(f'row {row_index}: digits must be positive')
        if point is not None and point <= 0:
            errors.append(f'row {row_index}: point must be positive')
        prices = [open_price, high_price, low_price, close_price]
        if all((price is not None for price in prices)):
            open_price_v = float(open_price)
            high_price_v = float(high_price)
            low_price_v = float(low_price)
            close_price_v = float(close_price)
            if min(open_price_v, high_price_v, low_price_v, close_price_v) <= 0:
                errors.append(f'row {row_index}: prices must be positive')
            if high_price_v < max(open_price_v, close_price_v, low_price_v):
                errors.append(f'row {row_index}: high must be >= max(open, close, low)')
            if low_price_v > min(open_price_v, close_price_v, high_price_v):
                errors.append(f'row {row_index}: low must be <= min(open, close, high)')
    status = ValidationStatus.VALID.value if not errors else ValidationStatus.INVALID.value
    return ValidationResult(status=status, errors=tuple(errors), row_count=row_count)
