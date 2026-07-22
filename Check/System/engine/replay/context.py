"""Dynamic market context for replay (no look-ahead, no fake low news)."""
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from engine.core.clock import format_utc_timestamp
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.constants import PROTOCOL_SCHEMA_VERSION, REASON_NEWS_DATA_UNAVAILABLE, MarketRegime
from engine.protocol.models import UniverseRecord

# Matches tests/mql4/status_reference.detect_trading_session (UTC hours).
_SESSION_ASIA = 'ASIA'
_SESSION_LONDON = 'LONDON'
_SESSION_NEW_YORK = 'NEW_YORK'
_SESSION_OFF = 'OFF'


def detect_session(timestamp: datetime, *, timezone_name: str = 'UTC') -> str:
    """Session label from candle timestamp and configured timezone."""
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    local = timestamp.astimezone(ZoneInfo(timezone_name))
    hour = local.hour
    if 0 <= hour < 8:
        return _SESSION_ASIA
    if 8 <= hour < 13:
        return _SESSION_LONDON
    if 13 <= hour < 22:
        return _SESSION_NEW_YORK
    return _SESSION_OFF


def _true_range(bar: NormalizedMarketBar, prev_close: float | None) -> float:
    if prev_close is None:
        return max(0.0, bar.high - bar.low)
    return max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))


def detect_regime_from_bars(bars: tuple[NormalizedMarketBar, ...], *, lookback: int = 20) -> str:
    """Market regime from past+current bars only (no future candles)."""
    if len(bars) < 3:
        return MarketRegime.RANGING.value
    window = bars[-lookback:] if len(bars) > lookback else bars
    ranges = [max(0.0, bar.high - bar.low) for bar in window]
    sorted_ranges = sorted(ranges)
    mid = len(sorted_ranges) // 2
    if len(sorted_ranges) % 2:
        median_range = sorted_ranges[mid]
    else:
        median_range = (sorted_ranges[mid - 1] + sorted_ranges[mid]) / 2.0
    prev_close: float | None = None
    trs: list[float] = []
    for bar in window:
        trs.append(_true_range(bar, prev_close))
        prev_close = bar.close
    atr = sum(trs) / len(trs) if trs else 0.0
    close_move = abs(window[-1].close - window[0].close)
    if median_range <= 0:
        return MarketRegime.RANGING.value
    if atr > 1.6 * median_range:
        return MarketRegime.VOLATILE.value
    if atr < 0.55 * median_range:
        return MarketRegime.QUIET.value
    if close_move > 2.0 * atr:
        return MarketRegime.TRENDING.value
    return MarketRegime.RANGING.value


def build_replay_universe(
    *,
    bars: tuple[NormalizedMarketBar, ...],
    timezone_name: str = 'UTC',
    news_events: tuple[dict[str, object], ...] | None = None,
    news_window_minutes: int = 30,
) -> tuple[UniverseRecord, dict[str, object]]:
    """Build universe for the latest bar in ``bars`` without look-ahead.

    When ``news_events`` is None/empty, news risk is marked unavailable — never
    assumed low.
    """
    last = bars[-1]
    ts = format_utc_timestamp(last.time_utc)
    session = detect_session(last.time_utc, timezone_name=timezone_name)
    regime = detect_regime_from_bars(bars)
    meta: dict[str, object] = {
        'news_status': 'available' if news_events else 'unavailable',
        'news_reason_code': None if news_events else REASON_NEWS_DATA_UNAVAILABLE,
        'news_filter_disabled': not bool(news_events),
        'timezone_name': timezone_name,
    }
    if not news_events:
        universe = UniverseRecord(
            schema_version=PROTOCOL_SCHEMA_VERSION,
            timestamp_utc=ts,
            session=session,
            market_regime=regime,
            news_window_active=False,
            news_impact_level=None,
        )
        return universe, meta

    active = False
    impact: str | None = None
    last_epoch = last.time_utc.timestamp()
    window_sec = max(0, int(news_window_minutes)) * 60
    for event in news_events:
        event_ts = event.get('time_utc')
        if not isinstance(event_ts, str):
            continue
        try:
            parsed = datetime.fromisoformat(event_ts.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            event_epoch = parsed.astimezone(timezone.utc).timestamp()
        except ValueError:
            continue
        if abs(event_epoch - last_epoch) <= window_sec:
            active = True
            level = str(event.get('impact_level', 'medium')).lower()
            if impact is None or level == 'high' or (impact != 'high' and level == 'medium'):
                impact = level
    universe = UniverseRecord(
        schema_version=PROTOCOL_SCHEMA_VERSION,
        timestamp_utc=ts,
        session=session,
        market_regime=regime,
        news_window_active=active,
        news_impact_level=impact,
    )
    meta['news_status'] = 'available'
    meta['news_filter_disabled'] = False
    return universe, meta
