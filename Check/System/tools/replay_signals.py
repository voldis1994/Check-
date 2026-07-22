#!/usr/bin/env python3
"""Replay market CSV bars through the decision engine (no MT4 commands).

Usage:
  cd Check/System
  python tools/replay_signals.py --market path/to/market_EURUSD_100001.csv
  python tools/replay_signals.py --market path/to/market.csv --config config/system.json
"""
from __future__ import annotations
import argparse
import sys
from collections import Counter
from pathlib import Path
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.core.config import load_system_config
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.decision.engine import run_decision_engine
from engine.normalizer.market_normalizer import normalize_market_csv
from engine.protocol.constants import Decision, PROTOCOL_SCHEMA_VERSION
from engine.protocol.models import UniverseRecord
from engine.state.instance_state import InstanceState
MODULE_NAME = 'tools.replay_signals'

def _default_universe() -> UniverseRecord:
    return UniverseRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', session='LONDON', market_regime='trending', news_window_active=False, news_impact_level='low')

def _extract_reason_code(reason: str, signal_quality_reason: str | None) -> str:
    if signal_quality_reason:
        return signal_quality_reason
    if ':' in reason:
        return reason.split(':', 1)[0].strip()
    return reason.strip() or 'NONE'

def replay_market_csv(*, market_path: Path, config_path: Path | None=None, account_id: str='replay', magic: int=100001, relative_spread: float=1.0, min_bars: int | None=None) -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    system_config = load_system_config(config_path or root / 'config' / 'system.json', system_paths=SystemPaths(root))
    raw_text = market_path.read_text(encoding='utf-8')
    bars = normalize_market_csv(raw_text)
    if not bars:
        raise SystemExit(f'no bars in {market_path}')
    lookback = max(3, int(system_config.analysis.lookback_bars))
    structure_lookback = max(2, int(system_config.analysis.structure_lookback_bars))
    required = max(3, min_bars or 3)
    if len(bars) < required:
        raise SystemExit(f'need at least {required} bars, found {len(bars)} in {market_path}')
    # Prefer full lookback when available; otherwise start as soon as the CSV has enough bars.
    preferred = max(structure_lookback, lookback)
    start_index = preferred if len(bars) >= preferred else required
    symbol = bars[0].symbol
    instance = Instance(account_id=account_id, symbol=symbol, magic=magic)
    instance_state = InstanceState(instance=instance)
    instance_state.update_instrument(digits=bars[0].digits, point=bars[0].point, pip=bars[0].point * 10.0 if bars[0].digits >= 3 else bars[0].point)
    universe = _default_universe()
    decision_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    evaluated = 0
    for end in range(start_index, len(bars) + 1):
        window = tuple(bars[:end])
        result = run_decision_engine(universe=universe, market_bars=window, instance_state=instance_state, relative_spread=relative_spread, system_config=system_config, execution_possible=True)
        evaluated += 1
        decision_counts[result.decision] += 1
        quality = result.signal_quality
        reason_code = _extract_reason_code(result.reason, quality.reason_code if quality is not None else None)
        reason_counts[reason_code] += 1
    return {
        'market_path': str(market_path),
        'bars_total': len(bars),
        'windows_evaluated': evaluated,
        'decisions': dict(decision_counts),
        'reason_codes': dict(reason_counts),
        'buy': decision_counts.get(Decision.BUY.value, 0),
        'sell': decision_counts.get(Decision.SELL.value, 0),
        'wait': decision_counts.get(Decision.WAIT.value, 0),
        'block': decision_counts.get(Decision.BLOCK.value, 0),
    }

def format_summary(summary: dict[str, object]) -> str:
    lines = [
        f"replay market={summary['market_path']}",
        f"bars={summary['bars_total']} windows={summary['windows_evaluated']}",
        f"BUY={summary['buy']} SELL={summary['sell']} WAIT={summary['wait']} BLOCK={summary['block']}",
        'reason codes:',
    ]
    reason_codes = summary.get('reason_codes')
    if isinstance(reason_codes, dict):
        for code, count in sorted(reason_codes.items(), key=lambda item: (-int(item[1]), str(item[0]))):
            lines.append(f'  {code}: {count}')
    return '\n'.join(lines)

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description='Replay market CSV through decision engine (no MT4 commands)')
    parser.add_argument('--market', required=True, help='Path to market_*.csv')
    parser.add_argument('--config', default=None, help='Optional system.json path')
    parser.add_argument('--account-id', default='replay')
    parser.add_argument('--magic', type=int, default=100001)
    parser.add_argument('--relative-spread', type=float, default=1.0)
    args = parser.parse_args(argv)
    market_path = Path(args.market).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve() if args.config else None
    summary = replay_market_csv(market_path=market_path, config_path=config_path, account_id=args.account_id, magic=args.magic, relative_spread=args.relative_spread)
    print(format_summary(summary), flush=True)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
