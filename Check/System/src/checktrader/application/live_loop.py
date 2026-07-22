"""Live loop — one process, every discovered MT4 account/bridge."""

from __future__ import annotations

import time
from pathlib import Path

from checktrader.application.account_resolve import account_is_allowed
from checktrader.application.bootstrap import bootstrap
from checktrader.application.cycle import run_cycle
from checktrader.domain.errors import DataError
from checktrader.execution.bridge_discover import bridge_wait_hint, list_active_bridges
from checktrader.execution.snapshot_select import select_latest_snapshot
from checktrader.market_data.loader import parse_market_snapshot
from checktrader.market_data.status import parse_status_snapshot
from checktrader.observability.logging import get_logger
from checktrader.state.store import InstanceRuntimeState, account_state_path, load_instance_state, save_instance_state


def run_trading_loop(*, config_path: Path, once: bool = False, require_live_accounts: bool = True) -> None:
    logger = get_logger("checktrader.live")
    config, _legacy_state, root = bootstrap(config_path, require_live_accounts=require_live_accounts)
    configured_bridge = (root / config.paths.bridge).resolve()
    stop_file = root / "runtime" / "STOP_TRADING"
    wait_logs = 0
    states: dict[str, InstanceRuntimeState] = {}
    announced: set[str] = set()

    def state_for(account: str) -> tuple[InstanceRuntimeState, Path]:
        path = account_state_path(root, config.paths.state, account)
        if account not in states:
            path.parent.mkdir(parents=True, exist_ok=True)
            loaded = load_instance_state(path)
            # One-time migrate from legacy single instance.json when first account appears.
            legacy = root / config.paths.state / "instance.json"
            if (
                not path.exists()
                and legacy.exists()
                and not any((root / config.paths.state / "accounts").glob("*.json"))
                and len(states) == 0
            ):
                loaded = load_instance_state(legacy)
            states[account] = loaded
            if account not in announced:
                announced.add(account)
                logger.info("multi-account: tracking account=%s state=%s", account, path)
        return states[account], path

    while True:
        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        bridges = list_active_bridges(configured_bridge=configured_bridge)
        if not bridges:
            wait_logs += 1
            if wait_logs == 1 or wait_logs % 20 == 0:
                logger.warning("waiting for market/status bridge files (no active MT4 bridges)")
                logger.warning("%s", bridge_wait_hint(configured_bridge))
            if once:
                return
            time.sleep(max(config.runtime.cycle_interval_ms / 1000.0, 0.5))
            continue
        wait_logs = 0

        seen_accounts: set[str] = set()
        for bridge_loc in bridges:
            bridge = bridge_loc.bridge_root
            market_choice = select_latest_snapshot(bridge / "market")
            status_choice = select_latest_snapshot(bridge / "status")
            if market_choice is None or status_choice is None:
                continue
            try:
                market = parse_market_snapshot(market_choice.payload)
                status = parse_status_snapshot(status_choice.payload)
            except (DataError, KeyError, TypeError, ValueError) as exc:
                logger.warning("skip bridge=%s parse_error=%s", bridge_loc.source, exc)
                continue

            account = str(status.account_number or "").strip()
            if not account:
                continue
            if account in seen_accounts:
                # Same account on two bridges in one tick — keep freshest (already sorted).
                continue
            seen_accounts.add(account)

            if not account_is_allowed(config, account):
                logger.info(
                    "cycle reason=ACCOUNT_NOT_ALLOWED action=NONE symbol=%s account=%s bridge=%s",
                    market.specs.symbol,
                    account,
                    bridge_loc.source,
                )
                continue

            state, state_path = state_for(account)
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
                state_path=state_path,
            )
            logger.info(
                "cycle reason=%s action=%s symbol=%s account=%s bridge=%s",
                result.reason.value,
                result.action.value,
                market.specs.symbol,
                account,
                bridge_loc.source,
            )
            save_instance_state(state_path, state, now_utc=now)

        if once:
            return
        time.sleep(config.runtime.cycle_interval_ms / 1000.0)
