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
    config: SystemConfig; specs: SymbolSpecs; state: RuntimeState; history: RollingHistory; state_store: StateStore; detector: RegimeDetector; router: StrategyRouter; execution: ExecutionCoordinator; audit: AuditWriter; metrics: Metrics
def symbol_specs(config: SystemConfig) -> SymbolSpecs:
    return SymbolSpecs(config.instrument.symbol,config.instrument.digits,config.instrument.point,config.instrument.pip_size,config.position_sizing.min_lot,config.position_sizing.max_lot,config.position_sizing.lot_step,config.instrument.contract_size,config.instrument.stop_level_points,config.instrument.freeze_level_points)
def bootstrap(config_path: str|Path, *, mode_override: str|None=None, bridge_dir: Path|None=None) -> AppContext:
    schema=Path('config/system.schema.json'); config=load_config(config_path, schema if schema.exists() else None, validate_live=False)
    if mode_override is not None: config=config.model_copy(update={'runtime':config.runtime.model_copy(update={'mode':mode_override})})
    validate_runtime_safety(config); config.paths.runtime_dir.mkdir(parents=True,exist_ok=True)
    history=load_history(config.paths.history_file,{'M1':config.limits.history_max_bars_m1,'M5':config.limits.history_max_bars_m5,'M15':config.limits.history_max_bars_m15}); state=recover_state(config)
    return AppContext(config,symbol_specs(config),state,history,StateStore(config.paths.state_file),RegimeDetector(config),StrategyRouter(),ExecutionCoordinator(config,bridge_dir or config.paths.bridge_dir),AuditWriter(config.paths.audit_file),Metrics())
