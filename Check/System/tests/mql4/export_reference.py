from __future__ import annotations
from engine.protocol.constants import MARKET_CSV_COLUMNS, SENSOR_CSV_COLUMNS, TIMEFRAME_M1

def timeframe_m1() -> str:
    return TIMEFRAME_M1

def market_csv_header() -> str:
    return ','.join(MARKET_CSV_COLUMNS)

def sensor_csv_header() -> str:
    return ','.join(SENSOR_CSV_COLUMNS)

def build_market_file_path(root_path: str, account_id: str, symbol: str, magic: int) -> str:
    return f'{root_path}\\data\\clients\\{account_id}\\market_{symbol}_{magic}.csv'

def build_sensor_file_path(root_path: str, account_id: str, symbol: str, magic: int) -> str:
    return f'{root_path}\\data\\clients\\{account_id}\\sensor_{symbol}_{magic}.csv'

def format_csv_number(value: float, digits: int) -> str:
    return f'{value:.{digits}f}'

def calculate_spread(bid: float, ask: float) -> float:
    return ask - bid

def calculate_spread_points(spread: float, point: float) -> float:
    if point <= 0.0:
        return 0.0
    return spread / point

def build_market_csv_row(*, time_utc: str, open_price: float, high_price: float, low_price: float, close_price: float, volume: float, symbol: str, digits: int, point: float) -> str:
    return ','.join([time_utc, format_csv_number(open_price, digits), format_csv_number(high_price, digits), format_csv_number(low_price, digits), format_csv_number(close_price, digits), format_csv_number(volume, 0), symbol, timeframe_m1(), str(digits), format_csv_number(point, digits)])

def build_sensor_csv_row(*, time_utc: str, bid: float, ask: float, symbol: str, digits: int, point: float) -> str:
    spread = calculate_spread(bid, ask)
    spread_points = calculate_spread_points(spread, point)
    return ','.join([time_utc, format_csv_number(bid, digits), format_csv_number(ask, digits), format_csv_number(spread, digits), format_csv_number(spread_points, 0), symbol, str(digits), format_csv_number(point, digits)])

def csv_contains_time_utc(csv_content: str, time_utc: str) -> bool:
    if not time_utc:
        return False
    needle = f'{time_utc},'
    if csv_content.startswith(needle):
        return True
    return f'\n{needle}' in csv_content

def append_csv_row(csv_content: str, header: str, row: str) -> str:
    time_utc = row.split(',', 1)[0]
    if not csv_content:
        return f'{header}\n{row}\n'
    if csv_contains_time_utc(csv_content, time_utc):
        return csv_content
    normalized = csv_content if csv_content.endswith('\n') else f'{csv_content}\n'
    return f'{normalized}{row}\n'
