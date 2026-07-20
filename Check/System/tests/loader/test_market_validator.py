from __future__ import annotations
from pathlib import Path
from engine.validator.market_validator import validate_market_csv
FIXTURES_DIR = Path(__file__).parent / 'fixtures'

def test_market_validator_valid_market_is_valid() -> None:
    raw_text = (FIXTURES_DIR / 'market_valid.csv').read_text(encoding='utf-8')
    result = validate_market_csv(raw_text)
    assert result.is_valid
    assert result.row_count == 2
    assert result.errors == ()

def test_market_validator_broken_ohlc_is_invalid() -> None:
    raw_text = 'time_utc,open,high,low,close,volume,symbol,timeframe,digits,point\n2026-07-07T06:00:00.000Z,1.10000,1.09000,1.08000,1.09500,120,EURUSD,M1,5,0.00001\n'
    result = validate_market_csv(raw_text)
    assert not result.is_valid
    assert any(('high must be >=' in error for error in result.errors))

def test_market_validator_missing_column_is_invalid() -> None:
    raw_text = (FIXTURES_DIR / 'market_missing.csv').read_text(encoding='utf-8')
    result = validate_market_csv(raw_text)
    assert not result.is_valid
    assert result.row_count == 0
    assert 'missing or invalid market csv columns' in result.errors

def test_market_validator_non_m1_timeframe_is_invalid() -> None:
    raw_text = 'time_utc,open,high,low,close,volume,symbol,timeframe,digits,point\n2026-07-07T06:00:00.000Z,1.08500,1.08600,1.08400,1.08550,120,EURUSD,H1,5,0.00001\n'
    result = validate_market_csv(raw_text)
    assert not result.is_valid
    assert any(('timeframe must be M1' in error for error in result.errors))

def test_market_validator_duplicate_times_are_invalid() -> None:
    raw_text = 'time_utc,open,high,low,close,volume,symbol,timeframe,digits,point\n2026-07-07T06:00:00.000Z,1.08500,1.08600,1.08400,1.08550,120,EURUSD,M1,5,0.00001\n2026-07-07T06:00:00.000Z,1.08550,1.08650,1.08500,1.08600,98,EURUSD,M1,5,0.00001\n'
    result = validate_market_csv(raw_text)
    assert not result.is_valid
    assert any(('duplicate time_utc' in error for error in result.errors))

def test_sanitize_market_csv_repairs_out_of_order_and_duplicates() -> None:
    from engine.validator.market_validator import sanitize_market_csv
    raw_text = (
        'time_utc,open,high,low,close,volume,symbol,timeframe,digits,point\n'
        '2026-07-07T06:02:00.000Z,1.08700,1.08800,1.08600,1.08750,100,EURUSD,M1,5,0.00001\n'
        '2026-07-07T06:00:00.000Z,1.08500,1.08600,1.08400,1.08550,120,EURUSD,M1,5,0.00001\n'
        '2026-07-07T06:00:00.000Z,1.08510,1.08610,1.08410,1.08560,121,EURUSD,M1,5,0.00001\n'
        '2026-07-07T06:01:00.000Z,1.08600,1.08700,1.08500,1.08650,110,EURUSD,M1,5,0.00001\n'
    )
    sanitized = sanitize_market_csv(raw_text)
    assert sanitized.changed is True
    assert sanitized.dropped_duplicates == 1
    assert sanitized.reordered is True
    assert sanitized.row_count == 3
    validated = validate_market_csv(sanitized.raw_text)
    assert validated.is_valid
    lines = [line for line in sanitized.raw_text.splitlines() if line.strip()]
    assert lines[1].startswith('2026-07-07T06:00:00.000Z,1.08510')
    assert lines[2].startswith('2026-07-07T06:01:00.000Z')
    assert lines[3].startswith('2026-07-07T06:02:00.000Z')

def test_sanitize_market_csv_no_change_when_already_ordered() -> None:
    from engine.validator.market_validator import sanitize_market_csv
    raw_text = (FIXTURES_DIR / 'market_valid.csv').read_text(encoding='utf-8')
    sanitized = sanitize_market_csv(raw_text)
    assert sanitized.changed is False
    assert sanitized.dropped_duplicates == 0
    assert sanitized.reordered is False
