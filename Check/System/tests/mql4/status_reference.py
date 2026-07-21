from __future__ import annotations
import json
from engine.protocol.constants import PROTOCOL_SCHEMA_VERSION

def protocol_schema_version() -> str:
    return PROTOCOL_SCHEMA_VERSION

def ea_version() -> str:
    return '1.1.5'

def format_json_boolean(value: bool) -> str:
    return 'true' if value else 'false'

def format_json_number(value: float, digits: int) -> str:
    return f'{value:.{digits}f}'

def escape_json_string(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"')

def build_status_file_path(root_path: str, account_id: str) -> str:
    return f'{root_path}\\data\\clients\\{account_id}\\status_{account_id}.json'

def build_status_json(*, account_id: str, connected: bool, trade_allowed: bool, balance: float, equity: float, margin_free: float, timestamp_utc: str, symbol: str='EURUSD', magic: int=100001, last_error: str | None=None, open_positions: list[dict[str, object]] | None=None) -> str:
    payload: dict[str, object] = {'account_id': account_id, 'balance': balance, 'connected': connected, 'ea_version': ea_version(), 'equity': equity, 'margin_free': margin_free, 'schema_version': protocol_schema_version(), 'timestamp_utc': timestamp_utc, 'trade_allowed': trade_allowed}
    if last_error:
        payload['last_error'] = last_error
    if open_positions:
        payload['open_positions'] = open_positions
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n'

def build_universe_file_path(root_path: str, account_id: str) -> str:
    return f'{root_path}\\data\\clients\\{account_id}\\universe.json'

def detect_trading_session(hour_utc: int) -> str:
    if 0 <= hour_utc < 8:
        return 'ASIA'
    if 8 <= hour_utc < 13:
        return 'LONDON'
    if 13 <= hour_utc < 22:
        return 'NEW_YORK'
    return 'OFF'

def detect_market_regime(*, atr: float, median_range: float, close_move: float) -> str:
    if median_range <= 0:
        return 'ranging'
    if atr > 1.6 * median_range:
        return 'volatile'
    if atr < 0.55 * median_range:
        return 'quiet'
    if abs(close_move) > 2.0 * atr:
        return 'trending'
    return 'ranging'

def build_universe_json(*, session: str, market_regime: str, news_window_active: bool, timestamp_utc: str, news_impact_level: str | None='low', metadata: dict[str, object] | None=None) -> str:
    payload: dict[str, object] = {'market_regime': market_regime, 'news_window_active': news_window_active, 'schema_version': protocol_schema_version(), 'session': session, 'timestamp_utc': timestamp_utc}
    if news_impact_level:
        payload['news_impact_level'] = news_impact_level
    if metadata is not None:
        payload['metadata'] = metadata
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
