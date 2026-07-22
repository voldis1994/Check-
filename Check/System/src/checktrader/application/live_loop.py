"""Live loop."""

from __future__ import annotations

import time
from pathlib import Path

from checktrader.application.bootstrap import bootstrap
from checktrader.application.cycle import run_cycle
from checktrader.execution.bridge_discover import bridge_wait_hint, resolve_bridge_directory
from checktrader.execution.snapshot_select import select_latest_snapshot
from checktrader.market_data.loader import parse_market_snapshot
from checktrader.market_data.status import parse_status_snapshot
from checktrader.observability.logging import get_logger
from checktrader.state.store import save_instance_state


def run_trading_loop(*, config_path: Path, once: bool = False, require_live_accounts: bool = True) -> None:
    logger = get_logger("checktrader.live")
    config, state, root = bootstrap(config_path, require_live_accounts=require_live_accounts)
    configured_bridge = (root / config.paths.bridge).resolve()
    stop_file = root / "runtime" / "STOP_TRADING"
    wait_logs = 0
    while True:
        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        bridge_loc = resolve_bridge_directory(configured_bridge=configured_bridge)
        bridge = bridge_loc.bridge_root
        market_choice = select_latest_snapshot(bridge / "market")
        status_choice = select_latest_snapshot(bridge / "status")
        if market_choice is None or status_choice is None:
            wait_logs += 1
            if wait_logs == 1 or wait_logs % 20 == 0:
                logger.warning(
                    "waiting for market/status bridge files (source=%s path=%s)",
                    bridge_loc.source,
                    bridge,
                )
                logger.warning("%s", bridge_wait_hint(configured_bridge))
            if once:
                return
            time.sleep(max(config.runtime.cycle_interval_ms / 1000.0, 0.5))
            continue
        wait_logs = 0
        # Ignore stale/repeated sequences as "new" work, but still process pending with latest data.
        market = parse_market_snapshot(market_choice.payload)
        status = parse_status_snapshot(status_choice.payload)
        state.last_market_sequence = max(state.last_market_sequence, market_choice.sequence)
        state.last_status_sequence = max(state.last_status_sequence, status_choice.sequence)
        result = run_cycle(
            config=config,
            state=state,
            market=market,
            status=status,
            bridge_root=bridge,
            now_utc=now,
            kill_switch=stop_file.exists(),
        )
        logger.info(
            "cycle reason=%s action=%s symbol=%s account=%s bridge=%s",
            result.reason.value,
            result.action.value,
            market.specs.symbol,
            status.account_number,
            bridge_loc.source,
        )
        save_instance_state(root / config.paths.state / "instance.json", state, now_utc=now)
        if once:
            return
        time.sleep(config.runtime.cycle_interval_ms / 1000.0)
