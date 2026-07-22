from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterable
from pathlib import Path

from checktrader.app.bootstrap import AppContext
from checktrader.app.cycle import run_cycle
from checktrader.bridge.reader import read_market, read_positions, read_status
from checktrader.domain.enums import ReasonCode
from checktrader.domain.models import CycleAudit

logger = logging.getLogger(__name__)

_STOP_FILE = "STOP_TRADING"


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

    # Caller-supplied discovery roots
    patterns = ("**/Files/CHECK_SYSTEM", "**/Files/CHECK_SYSTEM_V3")
    for root in roots:
        for pattern in patterns:
            for base in root.glob(pattern):
                if base.is_dir():
                    candidates.append(base / "runtime" / "bridge")

    # APPDATA MetaQuotes Terminal discovery (Windows path convention)
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


def run_once(context: AppContext, bridge_dir: Path | None = None) -> CycleAudit:
    is_live = context.config.runtime.mode == "live"

    if not is_live and bridge_dir is None:
        # Pure paper mode, no bridge — run synthetic cycle
        return run_cycle(context)

    bridge = bridge_dir or context.config.paths.bridge_dir
    if bridge is None:
        if is_live:
            # Live mode with no bridge is an error; cycle.py will record BRIDGE_UNAVAILABLE
            return run_cycle(context, None)
        return run_cycle(context)

    try:
        market = read_market(bridge, context.specs.symbol)
    except Exception:  # noqa: BLE001 - bridge I/O must not kill the loop
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
    runtime_dir = context.config.paths.runtime_dir
    is_live = context.config.runtime.mode == "live"

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
            # Do NOT fall back to paper trading in live mode
            time.sleep(context.config.runtime.cycle_interval_seconds)
            continue

        try:
            if not is_live and not bridges:
                # Paper mode without any bridge — run a plain paper cycle
                run_once(context)
            else:
                for bridge in bridges or (
                    [] if context.config.paths.bridge_dir is None else [context.config.paths.bridge_dir]
                ):
                    try:
                        audit = run_once(context, bridge)
                    except Exception:  # noqa: BLE001
                        logger.exception("cycle failed for bridge %s", bridge)
                        continue
                    if audit.reason_code in {ReasonCode.BRIDGE_UNAVAILABLE, ReasonCode.DATA_STALE}:
                        logger.warning("cycle skipped: %s", audit.human_readable_reason)
        except Exception:  # noqa: BLE001
            logger.exception("cycle iteration failed")

        time.sleep(context.config.runtime.cycle_interval_seconds)
