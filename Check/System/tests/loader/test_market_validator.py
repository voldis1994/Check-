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
