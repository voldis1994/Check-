from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from checktrader.config.loader import load_config
from checktrader.config.models import SystemConfig
from checktrader.config.validation import validate_runtime_safety
from checktrader.domain.models import SymbolSpecs
from checktrader.execution.coordinator import ExecutionCoordinator
from checktrader.market_data.history import RollingHistory, load_history
from checktrader.observability.audit import AuditWriter
from checktrader.observability.metrics import Metrics
from checktrader.regimes.detector import RegimeDetector
from checktrader.state.recovery import recover_state
from checktrader.state.store import RuntimeState, StateStore
from checktrader.strategies.router import StrategyRouter


@dataclass(slots=True)
class AppContext:
    config: SystemConfig
    specs: SymbolSpecs
    state: RuntimeState
    history: RollingHistory
    state_store: StateStore
    detector: RegimeDetector
    router: StrategyRouter
    execution: ExecutionCoordinator
    audit: AuditWriter
    metrics: Metrics


def symbol_specs(config: SystemConfig) -> SymbolSpecs:
    return SymbolSpecs(
        config.instrument.symbol,
        config.instrument.digits,
        config.instrument.point,
        config.instrument.tick_size,
        config.instrument.pip_size,
        config.position_sizing.min_lot,
        config.position_sizing.max_lot,
        config.position_sizing.lot_step,
        config.instrument.contract_size,
        config.instrument.stop_level_points,
        config.instrument.freeze_level_points,
    )


def bootstrap(
    config_path: str | Path, *, mode_override: str | None = None, bridge_dir: Path | None = None
) -> AppContext:
    schema = Path("config/system.schema.json")
    config = load_config(config_path, schema if schema.exists() else None, validate_live=False)
    if mode_override is not None:
        config = config.model_copy(update={"runtime": config.runtime.model_copy(update={"mode": mode_override})})
    validate_runtime_safety(config)
    config.paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    history = load_history(
        config.paths.history_file,
        {
            "M1": config.limits.history_max_bars_m1,
            "M5": config.limits.history_max_bars_m5,
            "M15": config.limits.history_max_bars_m15,
        },
    )
    state = recover_state(config)
    return AppContext(
        config,
        symbol_specs(config),
        state,
        history,
        StateStore(config.paths.state_file),
        RegimeDetector(config),
        StrategyRouter(),
        ExecutionCoordinator(
            config,
            bridge_dir or config.paths.bridge_dir,
            config.paths.runtime_dir / "state" / "dedupe.json",
        ),
        AuditWriter(config.paths.audit_file),
        Metrics(),
    )


def spawn_account_context(base: AppContext, *, account_id: str, bridge_dir: Path) -> AppContext:
    """
    Isolated context for one MT4 account.

    Keeps shared audit stream, but separate history/state/dedupe/execution bridge
    so two terminals never corrupt each other's bars or positions.
    """
    acc_dir = base.config.paths.runtime_dir / "accounts" / account_id
    acc_dir.mkdir(parents=True, exist_ok=True)
    history_file = acc_dir / "history.json"
    state_file = acc_dir / "state.json"
    dedupe_file = acc_dir / "dedupe.json"
    metrics_file = acc_dir / "metrics.json"

    config = base.config.model_copy(
        deep=True,
        update={
            "paths": base.config.paths.model_copy(
                update={
                    "history_file": history_file,
                    "state_file": state_file,
                    "metrics_file": metrics_file,
                    "bridge_dir": bridge_dir,
                }
            ),
            "account": base.config.account.model_copy(update={"account_id": account_id}),
            "runtime": base.config.runtime.model_copy(
                update={"instance_id": f"{base.config.runtime.instance_id}-{account_id}"}
            ),
        },
    )

    history = load_history(
        history_file,
        {
            "M1": config.limits.history_max_bars_m1,
            "M5": config.limits.history_max_bars_m5,
            "M15": config.limits.history_max_bars_m15,
        },
    )
    state_store = StateStore(state_file)
    state = state_store.load(config.runtime.instance_id)
    return AppContext(
        config,
        symbol_specs(config),
        state,
        history,
        state_store,
        RegimeDetector(config),
        StrategyRouter(),
        ExecutionCoordinator(config, bridge_dir, dedupe_file),
        base.audit,
        Metrics(),
    )
