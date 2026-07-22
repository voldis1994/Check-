from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from checktrader.app.bootstrap import AppContext, spawn_account_context
from checktrader.app.cycle import merge_market_history, run_cycle
from checktrader.bridge.reader import read_market, read_positions, read_status
from checktrader.domain.enums import ReasonCode
from checktrader.domain.models import CycleAudit, MarketSnapshot
from checktrader.market_data.aggregation import aggregate_standard
from checktrader.market_data.bars import closed_bars
from checktrader.market_data.history import save_history
from checktrader.regimes.shared import SharedRegimeHub

logger = logging.getLogger(__name__)

_STOP_FILE = "STOP_TRADING"
_SAFE_ACCOUNT = re.compile(r"[^A-Za-z0-9._-]+")


def _stop_requested(runtime_dir: Path) -> bool:
    """Return True if a STOP_TRADING sentinel file exists under runtime_dir."""
    return (runtime_dir / _STOP_FILE).exists()


def discover_bridges(
    configured: Path | None, roots: Iterable[Path], *, include_appdata_metaquotes: bool = True
) -> list[Path]:
    """
    Discover usable bridge directories.

    A bridge is usable when it contains market/*.json (MT4 is exporting).
    Empty template folders like repo runtime/bridge are ignored.
    """
    candidates: list[Path] = []
    if configured is not None:
        candidates.append(configured)

    patterns = ("**/Files/CHECK_SYSTEM", "**/Files/CHECK_SYSTEM_V3")
    for root in roots:
        for pattern in patterns:
            for base in root.glob(pattern):
                if base.is_dir():
                    candidates.append(base / "runtime" / "bridge")

    if include_appdata_metaquotes and os.environ.get("APPDATA"):
        base_mq = Path(os.environ["APPDATA"]) / "MetaQuotes" / "Terminal"
        for pattern in ("**/MQL4/Files/CHECK_SYSTEM", "**/MQL4/Files/CHECK_SYSTEM_V3"):
            for base in base_mq.glob(pattern):
                if base.is_dir():
                    candidates.append(base / "runtime" / "bridge")

    ready: dict[str, Path] = {}
    for path in candidates:
        if not path.exists() or not path.is_dir():
            continue
        market_dir = path / "market"
        if not market_dir.is_dir():
            continue
        if not any(market_dir.glob("*.json")):
            continue
        ready[str(path.resolve())] = path.resolve()
    return list(ready.values())


def _market_mtime(bridge: Path) -> float:
    latest = bridge / "market" / "latest.json"
    if latest.exists():
        return latest.stat().st_mtime
    files = list((bridge / "market").glob("*.json"))
    if not files:
        return 0.0
    return max(p.stat().st_mtime for p in files)


def select_bridge(bridges: list[Path], sticky: Path | None = None, *, max_sticky_age_s: float = 90.0) -> Path | None:
    """Return freshest bridge (kept for helpers/tests). Multi-account loop uses all bridges."""
    if not bridges:
        return None
    now = time.time()
    ranked = sorted(bridges, key=_market_mtime, reverse=True)
    if sticky is not None:
        sticky_res = sticky.resolve()
        for bridge in bridges:
            if bridge.resolve() == sticky_res and (now - _market_mtime(bridge)) <= max_sticky_age_s:
                return bridge
    return ranked[0]


def safe_account_id(raw: str) -> str:
    cleaned = _SAFE_ACCOUNT.sub("_", raw.strip())
    return cleaned or "unknown"


def resolve_account_id(bridge: Path) -> str:
    """Prefer broker account from status/market; fall back to terminal folder id."""
    try:
        status = read_status(bridge)
    except Exception:  # noqa: BLE001
        status = None
    if status is not None and status.account_id:
        return safe_account_id(status.account_id)

    try:
        market = read_market(bridge, "AUTO")
    except Exception:  # noqa: BLE001
        market = None
    if market is not None:
        meta_acct = str((market.meta or {}).get("account_number") or "")
        if meta_acct:
            return safe_account_id(meta_acct)

    # .../Terminal/<HASH>/MQL4/Files/CHECK_SYSTEM/runtime/bridge
    parts = bridge.resolve().parts
    for i, part in enumerate(parts):
        if part == "Terminal" and i + 1 < len(parts):
            return safe_account_id(f"term-{parts[i + 1][:12]}")
    return safe_account_id(bridge.name)


@dataclass(slots=True)
class AccountSession:
    account_id: str
    bridge_dir: Path
    context: AppContext


class AccountSessionBook:
    """One isolated engine context per MT4 account/bridge."""

    def __init__(self, base: AppContext) -> None:
        self.base = base
        self._sessions: dict[str, AccountSession] = {}

    def get(self, bridge: Path) -> AccountSession:
        account_id = resolve_account_id(bridge)
        existing = self._sessions.get(account_id)
        if existing is not None:
            if existing.bridge_dir.resolve() != bridge.resolve():
                logger.info(
                    "account %s bridge moved %s -> %s",
                    account_id,
                    existing.bridge_dir,
                    bridge,
                )
                existing.bridge_dir = bridge
                existing.context.execution.bridge_dir = bridge
            return existing

        ctx = spawn_account_context(self.base, account_id=account_id, bridge_dir=bridge)
        session = AccountSession(account_id=account_id, bridge_dir=bridge, context=ctx)
        self._sessions[account_id] = session
        logger.info("multi-account session ready account=%s bridge=%s", account_id, bridge)
        return session

    @property
    def account_ids(self) -> list[str]:
        return sorted(self._sessions)


def run_once(
    context: AppContext,
    bridge_dir: Path | None = None,
    *,
    shared_regime=None,
) -> CycleAudit:
    is_live = context.config.runtime.mode == "live"

    if not is_live and bridge_dir is None:
        return run_cycle(context, shared_regime=shared_regime)

    bridge = bridge_dir or context.config.paths.bridge_dir
    if bridge is None:
        if is_live:
            return run_cycle(context, None, shared_regime=shared_regime)
        return run_cycle(context, shared_regime=shared_regime)

    try:
        market = read_market(bridge, context.specs.symbol)
    except Exception:  # noqa: BLE001
        logger.exception("failed reading market from %s", bridge)
        if is_live:
            return run_cycle(context, None, shared_regime=shared_regime)
        return run_cycle(context, shared_regime=shared_regime)

    if market is None:
        if is_live:
            logger.warning("bridge dir %s found but market data missing", bridge)
            return run_cycle(context, None, shared_regime=shared_regime)
        return run_cycle(context, shared_regime=shared_regime)

    try:
        market.account = read_status(bridge)
        market.positions = read_positions(bridge)
    except Exception:  # noqa: BLE001
        logger.exception("failed reading status/positions from %s", bridge)
    return run_cycle(context, market, shared_regime=shared_regime)


def _load_bridge_market(context: AppContext, bridge: Path) -> MarketSnapshot | None:
    try:
        market = read_market(bridge, context.specs.symbol)
    except Exception:  # noqa: BLE001
        logger.exception("failed reading market from %s", bridge)
        return None
    if market is None:
        return None
    try:
        market.account = read_status(bridge)
        market.positions = read_positions(bridge)
    except Exception:  # noqa: BLE001
        logger.exception("failed reading status/positions from %s", bridge)
    return market


def _seed_history_from_peer(context: AppContext, peer_m1: list) -> bool:
    """If peer has richer M1 for the same symbol, merge it so warm-up/regime match."""
    if not peer_m1:
        return False
    local = closed_bars(context.history.get("M1"))
    peer_closed = closed_bars(peer_m1)
    if len(peer_closed) <= len(local):
        return False
    context.history.merge("M1", peer_m1)
    m5_agg, m15_agg = aggregate_standard(context.history.get("M1"))
    context.history.merge("M5", m5_agg)
    context.history.merge("M15", m15_agg)
    save_history(context.config.paths.history_file, context.history)
    return True


def run_loop(context: AppContext) -> None:
    """Run forever: every discovered MT4 account/bridge gets its own cycle each tick."""
    runtime_dir = context.config.paths.runtime_dir
    is_live = context.config.runtime.mode == "live"
    book = AccountSessionBook(context)

    while True:
        if _stop_requested(runtime_dir):
            logger.info("STOP_TRADING file detected — exiting loop cleanly")
            break

        bridges = discover_bridges(
            context.config.paths.bridge_dir,
            context.config.paths.bridge_discovery_roots,
            include_appdata_metaquotes=context.config.paths.appdata_metaquotes_discovery,
        )

        if is_live and not bridges:
            logger.info("Live mode: no bridge directories found — waiting for MT4 to connect")
            time.sleep(context.config.runtime.cycle_interval_seconds)
            continue

        try:
            if not is_live and not bridges:
                run_once(context)
            else:
                ordered = sorted(bridges, key=_market_mtime, reverse=True)
                if not ordered and context.config.paths.bridge_dir is not None:
                    ordered = [context.config.paths.bridge_dir]
                logger.info(
                    "cycle tick bridges=%s accounts_known=%s",
                    len(ordered),
                    ",".join(book.account_ids) or "-",
                )

                # Pass 1: ingest each bridge into its isolated history.
                prepared: list[tuple[AccountSession, MarketSnapshot]] = []
                for bridge in ordered:
                    try:
                        session = book.get(bridge)
                        market = _load_bridge_market(session.context, bridge)
                        if market is None:
                            if is_live:
                                logger.warning("bridge dir %s found but market data missing", bridge)
                            continue
                        merge_market_history(session.context, market)
                        prepared.append((session, market))
                    except Exception:  # noqa: BLE001
                        logger.exception("ingest failed for bridge %s", bridge)

                # Pass 2: one shared regime per symbol from the richest M15 series.
                hub = SharedRegimeHub(context.config)
                tf = context.config.instrument.timeframe_decision
                for session, market in prepared:
                    hub.consider(
                        market.symbol or session.context.specs.symbol,
                        m1=session.context.history.get("M1"),
                        m15=session.context.history.get("M15"),
                        timeframe=tf,
                    )

                # Seed thinner accounts so both do not sit in HISTORY_INSUFFICIENT alone.
                for session, market in prepared:
                    symbol = market.symbol or session.context.specs.symbol
                    if _seed_history_from_peer(session.context, hub.best_m1(symbol)):
                        market.m1 = session.context.history.get("M1")
                        market.m5 = session.context.history.get("M5")
                        market.m15 = session.context.history.get("M15")
                        hub.consider(symbol, m1=market.m1, m15=market.m15, timeframe=tf)
                        logger.info(
                            "seeded history account=%s symbol=%s m1=%s m15=%s",
                            session.account_id,
                            symbol,
                            len(closed_bars(market.m1)),
                            len(closed_bars(market.m15)),
                        )

                hub.finalize()

                # Pass 3: trade/manage each account with the shared market regime.
                for session, market in prepared:
                    try:
                        symbol = market.symbol or session.context.specs.symbol
                        shared = hub.get(symbol)
                        audit = run_cycle(session.context, market, shared_regime=shared)
                    except Exception:  # noqa: BLE001
                        logger.exception("cycle failed for account %s", session.account_id)
                        continue
                    if audit.reason_code in {ReasonCode.BRIDGE_UNAVAILABLE, ReasonCode.DATA_STALE}:
                        logger.warning(
                            "cycle skipped account=%s reason=%s",
                            session.account_id,
                            audit.human_readable_reason,
                        )
                    else:
                        logger.info(
                            "cycle ok account=%s symbol=%s regime=%s reason=%s source=%s",
                            session.account_id,
                            audit.symbol,
                            audit.market_regime,
                            audit.reason_code,
                            (audit.metrics or {}).get("regime_source"),
                        )
        except Exception:  # noqa: BLE001
            logger.exception("cycle iteration failed")

        time.sleep(context.config.runtime.cycle_interval_seconds)
