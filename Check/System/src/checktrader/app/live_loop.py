from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from checktrader.app.bootstrap import AppContext, spawn_account_context
from checktrader.app.cycle import run_cycle
from checktrader.bridge.reader import read_market, read_positions, read_status
from checktrader.domain.enums import ReasonCode
from checktrader.domain.models import CycleAudit

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


def run_once(context: AppContext, bridge_dir: Path | None = None) -> CycleAudit:
    is_live = context.config.runtime.mode == "live"

    if not is_live and bridge_dir is None:
        return run_cycle(context)

    bridge = bridge_dir or context.config.paths.bridge_dir
    if bridge is None:
        if is_live:
            return run_cycle(context, None)
        return run_cycle(context)

    try:
        market = read_market(bridge, context.specs.symbol)
    except Exception:  # noqa: BLE001
        logger.exception("failed reading market from %s", bridge)
        if is_live:
            return run_cycle(context, None)
        return run_cycle(context)

    if market is None:
        if is_live:
            logger.warning("bridge dir %s found but market data missing", bridge)
            return run_cycle(context, None)
        return run_cycle(context)

    try:
        market.account = read_status(bridge)
        market.positions = read_positions(bridge)
    except Exception:  # noqa: BLE001
        logger.exception("failed reading status/positions from %s", bridge)
    return run_cycle(context, market)


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
                for bridge in ordered:
                    session: AccountSession | None = None
                    try:
                        session = book.get(bridge)
                        audit = run_once(session.context, session.bridge_dir)
                    except Exception:  # noqa: BLE001
                        logger.exception("cycle failed for bridge %s", bridge)
                        continue
                    account_id = session.account_id if session is not None else "?"
                    if audit.reason_code in {ReasonCode.BRIDGE_UNAVAILABLE, ReasonCode.DATA_STALE}:
                        logger.warning(
                            "cycle skipped account=%s reason=%s",
                            account_id,
                            audit.human_readable_reason,
                        )
                    else:
                        logger.info(
                            "cycle ok account=%s symbol=%s reason=%s",
                            account_id,
                            audit.symbol,
                            audit.reason_code,
                        )
        except Exception:  # noqa: BLE001
            logger.exception("cycle iteration failed")

        time.sleep(context.config.runtime.cycle_interval_seconds)
