from __future__ import annotations
import os, time
from pathlib import Path
from typing import Iterable
from checktrader.app.bootstrap import AppContext
from checktrader.app.cycle import run_cycle
from checktrader.bridge.reader import read_market, read_positions, read_status

def discover_bridges(configured: Path|None, roots: Iterable[Path], *, include_appdata_metaquotes: bool=True) -> list[Path]:
    candidates=[]
    if configured is not None: candidates.append(configured)
    for root in roots: candidates.extend(p for p in root.glob('**/Files/CHECK_SYSTEM_V3') if p.is_dir())
    if include_appdata_metaquotes and os.environ.get('APPDATA'):
        base=Path(os.environ['APPDATA'])/'MetaQuotes'/'Terminal'; candidates.extend(p for p in base.glob('**/MQL4/Files/CHECK_SYSTEM_V3') if p.is_dir())
    return list({str(p.resolve()):p for p in candidates if p.exists()}.values())
def run_once(context: AppContext, bridge_dir: Path|None=None):
    if context.config.runtime.mode=='paper' and bridge_dir is None: return run_cycle(context)
    bridge=bridge_dir or context.config.paths.bridge_dir
    if bridge is None: return run_cycle(context)
    market=read_market(bridge,context.specs.symbol)
    if market is None: return run_cycle(context)
    market.account=read_status(bridge); market.positions=read_positions(bridge); return run_cycle(context,market)
def run_loop(context: AppContext) -> None:
    while True:
        bridges=discover_bridges(context.config.paths.bridge_dir,context.config.paths.bridge_discovery_roots,include_appdata_metaquotes=context.config.paths.appdata_metaquotes_discovery)
        if context.config.runtime.mode=='paper' and not bridges: run_once(context)
        else:
            for bridge in bridges or ([] if context.config.paths.bridge_dir is None else [context.config.paths.bridge_dir]): run_once(context,bridge)
        time.sleep(context.config.runtime.cycle_interval_seconds)
