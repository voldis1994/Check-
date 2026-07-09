from __future__ import annotations
from datetime import timezone
from pathlib import Path
import pytest
from engine.normalizer.market_normalizer import normalize_market_csv
from engine.protocol.errors import ValidationError
FIXTURES_DIR = Path(__file__).parent.parent / 'loader' / 'fixtures'

def test_normalize_market_csv_returns_normalized_m1_objects() -> None:
    raw_text = (FIXTURES_DIR / 'market_valid.csv').read_text(encoding='utf-8')
    normalized = normalize_market_csv(raw_text)
    assert len(normalized) == 2
    assert normalized[0].timeframe == 'M1'
    assert normalized[0].symbol == 'EURUSD'
    assert normalized[0].digits == 5
    assert normalized[0].point == 1e-05

def test_normalize_market_csv_converts_timestamps_to_utc_datetimes() -> None:
    raw_text = 'time_utc,open,high,low,close,volume,symbol,timeframe,digits,point\n2026-07-07T06:00:00.000Z,1.10000,1.10100,1.09900,1.10050,100,EURUSD,M1,5,0.00001\n'
    normalized = normalize_market_csv(raw_text)
    assert len(normalized) == 1
    assert normalized[0].time_utc.tzinfo == timezone.utc
    assert normalized[0].time_utc.isoformat() == '2026-07-07T06:00:00+00:00'

def test_normalize_market_csv_preserves_price_digits_precision() -> None:
    raw_text = 'time_utc,open,high,low,close,volume,symbol,timeframe,digits,point\n2026-07-07T06:00:00.000Z,1.1000049,1.1010051,1.0990049,1.1005051,100,EURUSD,M1,5,0.00001\n'
    normalized = normalize_market_csv(raw_text)
    assert len(normalized) == 1
    assert normalized[0].open == 1.1
    assert normalized[0].high == 1.10101
    assert normalized[0].low == 1.099
    assert normalized[0].close == 1.10051

def test_normalize_market_csv_assigns_bar_index_sequentially() -> None:
    raw_text = (FIXTURES_DIR / 'market_valid.csv').read_text(encoding='utf-8')
    normalized = normalize_market_csv(raw_text)
    assert [bar.bar_index for bar in normalized] == [0, 1]

def test_normalize_market_csv_raises_on_invalid_market_data() -> None:
    raw_text = 'time_utc,open,high,low,close,volume,symbol,timeframe,digits,point\n2026-07-07T06:00:00.000Z,1.10000,1.09000,1.08000,1.09500,120,EURUSD,M1,5,0.00001\n'
    with pytest.raises(ValidationError, match='market csv validation failed'):
        normalize_market_csv(raw_text)
