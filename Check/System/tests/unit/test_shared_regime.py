from __future__ import annotations

from datetime import UTC, datetime, timedelta

from checktrader.config.models import SystemConfig
from checktrader.domain.enums import MarketRegime, ReasonCode
from checktrader.domain.models import Candle
from checktrader.regimes.shared import SharedRegimeHub


def _m1_series(n: int, start: datetime | None = None) -> list[Candle]:
    t0 = start or datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
    out: list[Candle] = []
    price = 100.0
    for i in range(n):
        ts = t0 + timedelta(minutes=i)
        out.append(Candle(ts, price, price + 0.2, price - 0.1, price + 0.05, 1.0, "M1", True))
        price += 0.02
    return out


def _m15_from_m1(m1: list[Candle]) -> list[Candle]:
    from checktrader.market_data.aggregation import aggregate_m1

    return aggregate_m1(m1, "M15")


def test_shared_hub_picks_richest_m15_same_regime() -> None:
    cfg = SystemConfig()
    hub = SharedRegimeHub(cfg)
    rich_m1 = _m1_series(15 * 220)
    thin_m1 = _m1_series(15 * 40)
    rich_m15 = _m15_from_m1(rich_m1)
    thin_m15 = _m15_from_m1(thin_m1)
    assert len(rich_m15) > len(thin_m15)

    hub.consider("NATURALGAS", m1=thin_m1, m15=thin_m15)
    hub.consider("NATURALGAS", m1=rich_m1, m15=rich_m15)
    hub.finalize()

    snap = hub.get("naturalgas")
    assert snap is not None
    assert snap.metadata.get("regime_source") == "shared"
    assert snap.metadata.get("shared_m15") == len(rich_m15)
    # Thin account alone would still be HISTORY_INSUFFICIENT; shared must not be that.
    assert snap.reason != ReasonCode.HISTORY_INSUFFICIENT
    assert snap.regime != MarketRegime.UNKNOWN or snap.reason == ReasonCode.NO_CLOSED_BARS


def test_best_m1_exposes_richest_peer_feed() -> None:
    cfg = SystemConfig()
    hub = SharedRegimeHub(cfg)
    rich = _m1_series(500)
    thin = _m1_series(50)
    hub.consider("X", m1=thin, m15=_m15_from_m1(thin))
    hub.consider("X", m1=rich, m15=_m15_from_m1(rich))
    assert len(hub.best_m1("X")) == len(rich)
