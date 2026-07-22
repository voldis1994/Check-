"""Trend pullback break strategy (M15 context → M5 setup → M1 trigger)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from checktrader.config.models import StrategyConfig
from checktrader.domain.enums import SetupState, Side, StrategyResult
from checktrader.domain.market import Candle
from checktrader.domain.money import SymbolSpecs, round_price
from checktrader.domain.setup import Setup
from checktrader.market_data.aggregator import atr, hma, swing_points
from checktrader.observability.reason_codes import ReasonCode
from checktrader.strategy.setup_identity import build_setup_fingerprint


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    result: StrategyResult
    reason: ReasonCode
    setup: Setup | None = None
    evidence: dict[str, object] | None = None


def _closes(candles: list[Candle]) -> list[float]:
    return [c.close for c in candles]


def bars_since_origin(*, origin_utc: str, bars_m1: list[Candle]) -> int:
    """Count complete M1 bars at or after the setup origin timestamp."""
    count = 0
    for candle in bars_m1:
        if not candle.complete:
            continue
        if candle.open_time_utc >= origin_utc:
            count += 1
    return count


def is_setup_expired(*, origin_utc: str, bars_m1: list[Candle], setup_expiry_bars: int) -> bool:
    """True when complete M1 bars since origin exceed configured expiry."""
    if setup_expiry_bars < 0:
        return False
    return bars_since_origin(origin_utc=origin_utc, bars_m1=bars_m1) > setup_expiry_bars


def _bias_m15(candles: list[Candle], *, hma_period: int) -> Side | None:
    if len(candles) < max(hma_period + 2, 10):
        return None
    highs, lows = swing_points(candles, lookback=2)
    if len(highs) < 2 or len(lows) < 2:
        return None
    h1, h2 = highs[-2][1], highs[-1][1]
    l1, l2 = lows[-2][1], lows[-1][1]
    slope_now = hma(_closes(candles), hma_period)
    slope_prev = hma(_closes(candles[:-1]), hma_period)
    if slope_now is None or slope_prev is None:
        return None
    last = candles[-1].close
    if h2 > h1 and l2 > l1 and slope_now > slope_prev and last >= l2:
        return Side.BUY
    if h2 < h1 and l2 < l1 and slope_now < slope_prev and last <= h2:
        return Side.SELL
    return None


def evaluate_trend_pullback(
    *,
    symbol: str,
    specs: SymbolSpecs,
    m15: list[Candle],
    m5: list[Candle],
    m1: list[Candle],
    config: StrategyConfig,
    now_utc: str,
) -> StrategyDecision:
    if not m15 or not m5 or not m1:
        return StrategyDecision(StrategyResult.DATA_INVALID, ReasonCode.DATA_MISSING)
    if config.use_closed_bars_only and (not m1[-1].complete or not m5[-1].complete or not m15[-1].complete):
        return StrategyDecision(StrategyResult.DATA_INVALID, ReasonCode.BAR_INCOMPLETE)
    if len(m15) < config.minimum_structure_bars:
        return StrategyDecision(StrategyResult.NO_SIGNAL, ReasonCode.NO_SIGNAL, evidence={"why": "insufficient_m15"})

    bias = _bias_m15(m15, hma_period=config.hma_period)
    if bias is None:
        return StrategyDecision(StrategyResult.NO_SIGNAL, ReasonCode.NO_SIGNAL, evidence={"why": "unclear_m15"})

    atr_m5 = atr(m5, config.atr_period)
    hma_m5 = hma(_closes(m5), config.hma_period)
    if atr_m5 is None or hma_m5 is None:
        return StrategyDecision(StrategyResult.NO_SIGNAL, ReasonCode.NO_SIGNAL, evidence={"why": "indicators"})

    m5_last = m5[-1]
    pullback_ok = False
    invalidation = 0.0
    trigger = 0.0
    # Trigger levels exclude the current M5 bar so an M1 breakout can clear them.
    prior_m5 = m5[-4:-1] if len(m5) >= 4 else m5[:-1]
    if not prior_m5:
        return StrategyDecision(StrategyResult.NO_SIGNAL, ReasonCode.NO_SIGNAL, evidence={"why": "insufficient_m5"})
    if bias is Side.BUY:
        distance = abs(m5_last.close - hma_m5)
        pullback_ok = distance <= config.pullback_atr_distance * atr_m5 and m5_last.low <= hma_m5
        invalidation = min(c.low for c in m5[-5:])
        trigger = max(c.high for c in prior_m5)
    else:
        distance = abs(m5_last.close - hma_m5)
        pullback_ok = distance <= config.pullback_atr_distance * atr_m5 and m5_last.high >= hma_m5
        invalidation = max(c.high for c in m5[-5:])
        trigger = min(c.low for c in prior_m5)

    if not pullback_ok:
        return StrategyDecision(
            StrategyResult.NO_SIGNAL, ReasonCode.NO_SIGNAL, evidence={"why": "no_pullback", "bias": bias.value}
        )

    buffer = config.trigger_break_buffer_pips * specs.pip_size
    m1_last = m1[-1]
    triggered = False
    if bias is Side.BUY:
        triggered = m1_last.close >= trigger + buffer and m1_last.close > m1_last.open
        proposed_entry = m1_last.close
        proposed_sl = round_price(invalidation - specs.pip_size, specs.digits)
    else:
        triggered = m1_last.close <= trigger - buffer and m1_last.close < m1_last.open
        proposed_entry = m1_last.close
        proposed_sl = round_price(invalidation + specs.pip_size, specs.digits)

    context_id = f"M15:{m15[-3].open_time_utc}:{bias.value}"
    pullback_id = f"M5:{m5[-1].open_time_utc}:{round_price(hma_m5, specs.digits)}"
    origin = m5[-1].open_time_utc
    fingerprint = build_setup_fingerprint(
        setup_version="2.0.0",
        symbol=symbol,
        setup_type=config.enabled_setup,
        direction=bias,
        context_structure_id=context_id,
        pullback_structure_id=pullback_id,
        setup_origin_timestamp=origin,
        trigger_level=round_price(trigger, specs.digits),
        invalidation_level=round_price(invalidation, specs.digits),
        digits=specs.digits,
    )
    setup = Setup(
        setup_id=str(uuid4()),
        setup_type=config.enabled_setup,
        symbol=symbol,
        direction=bias,
        context_timeframe="M15",
        setup_timeframe="M5",
        entry_timeframe="M1",
        setup_origin_timestamp=origin,
        context_structure_id=context_id,
        pullback_structure_id=pullback_id,
        trigger_level=round_price(trigger, specs.digits),
        invalidation_level=round_price(invalidation, specs.digits),
        proposed_entry=round_price(proposed_entry, specs.digits),
        proposed_stop_loss=proposed_sl,
        created_at=now_utc,
        expires_at=now_utc,
        state=SetupState.ARMED if not triggered else SetupState.TRIGGERED,
        fingerprint=fingerprint,
        evidence={"bias": bias.value, "hma_m5": hma_m5, "atr_m5": atr_m5},
    )
    if not triggered:
        if is_setup_expired(
            origin_utc=origin,
            bars_m1=m1,
            setup_expiry_bars=config.setup_expiry_bars,
        ):
            setup.state = SetupState.EXPIRED
            return StrategyDecision(
                StrategyResult.NO_SIGNAL,
                ReasonCode.SETUP_EXPIRED,
                setup=setup,
                evidence=setup.evidence,
            )
        return StrategyDecision(StrategyResult.NO_SIGNAL, ReasonCode.SETUP_ARMED, setup=setup, evidence=setup.evidence)
    result = StrategyResult.ENTRY_BUY if bias is Side.BUY else StrategyResult.ENTRY_SELL
    reason = ReasonCode.ENTRY_BUY if bias is Side.BUY else ReasonCode.ENTRY_SELL
    return StrategyDecision(result, reason, setup=setup, evidence=setup.evidence)
