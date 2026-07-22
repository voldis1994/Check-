"""Live loop."""

from __future__ import annotations

import time
from pathlib import Path

from checktrader.application.bootstrap import bootstrap
from checktrader.application.cycle import run_cycle
from checktrader.execution.protocol import read_json
from checktrader.market_data.loader import parse_market_snapshot
from checktrader.market_data.status import parse_status_snapshot
from checktrader.observability.logging import get_logger
from checktrader.state.store import save_instance_state


def _latest_json(directory: Path) -> Path | None:
    files = sorted(directory.glob("*.json"))
    return files[-1] if files else None


def run_trading_loop(*, config_path: Path, once: bool = False, require_live_accounts: bool = True) -> None:
    logger = get_logger("checktrader.live")
    config, state, root = bootstrap(config_path, require_live_accounts=require_live_accounts)
    bridge = root / config.paths.bridge
    stop_file = root / "runtime" / "STOP_TRADING"
    while True:
        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        market_path = _latest_json(bridge / "market")
        status_path = _latest_json(bridge / "status")
        if market_path is None or status_path is None:
            logger.warning("waiting for market/status bridge files")
            if once:
                return
            time.sleep(config.runtime.cycle_interval_ms / 1000.0)
            continue
        market = parse_market_snapshot(read_json(market_path))
        status = parse_status_snapshot(read_json(status_path))
        result = run_cycle(
            config=config,
            state=state,
            market=market,
            status=status,
            bridge_root=bridge,
            now_utc=now,
            kill_switch=stop_file.exists(),
        )
        logger.info("cycle reason=%s action=%s", result.reason.value, result.action.value)
        save_instance_state(root / config.paths.state / "instance.json", state, now_utc=now)
        if once:
            return
        time.sleep(config.runtime.cycle_interval_ms / 1000.0)
