#!/usr/bin/env python3
"""Replay market CSV through the decision engine with stateful simulation (no MT4).

Usage:
  cd Check/System
  python tools/replay_signals.py --market path/to/market_EURUSD_100001.csv
  python tools/replay_signals.py --market path/to/market.csv --config config/system.json --output-dir /tmp/replay_out
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.replay.execution_model import ReplayExecutionConfig
from engine.replay.simulator import run_replay

MODULE_NAME = 'tools.replay_signals'


def format_summary(summary: dict[str, object]) -> str:
    lines = [
        f"replay market={summary.get('market_path')}",
        f"bars={summary.get('total_bars', summary.get('bars_total'))} evaluated={summary.get('evaluated_bars', summary.get('windows_evaluated'))}",
        f"BUY={summary.get('BUY_signal_count', summary.get('buy'))} SELL={summary.get('SELL_signal_count', summary.get('sell'))} WAIT={summary.get('WAIT_count', summary.get('wait'))} BLOCK={summary.get('BLOCK_count', summary.get('block'))}",
        f"WAIT%={summary.get('WAIT_percentage', 0):.1f} opened={summary.get('opened_trades', 0)} closed={summary.get('closed_trades', 0)}",
        f"wins={summary.get('wins', 0)} losses={summary.get('losses', 0)} BE={summary.get('breakeven', 0)} unknown={summary.get('unknown_outcomes', 0)}",
        f"net={summary.get('net_result', 0)} total_R={summary.get('total_R', 0)} expectancy={summary.get('expectancy', 0)}",
        f"duplicates={summary.get('duplicate_signal_rejection_count', 0)} cooldowns={summary.get('cooldown_rejection_count', 0)}",
        f"control_files_written={summary.get('control_files_written', 0)}",
        'reason codes:',
    ]
    reason_codes = summary.get('reason_codes')
    if isinstance(reason_codes, dict):
        for code, count in sorted(reason_codes.items(), key=lambda item: (-int(item[1]), str(item[0]))):
            lines.append(f'  {code}: {count}')
    return '\n'.join(lines)


def _load_news_file(path: Path | None) -> tuple[dict[str, object], ...] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(payload, list):
        return tuple(item for item in payload if isinstance(item, dict))
    events = payload.get('events') if isinstance(payload, dict) else None
    if isinstance(events, list):
        return tuple(item for item in events if isinstance(item, dict))
    raise SystemExit(f'news file must be a JSON list or object with events[]: {path}')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Replay market CSV with stateful simulation (no MT4 commands)')
    parser.add_argument('--market', required=True, help='Path to market_*.csv')
    parser.add_argument('--config', default=None, help='Optional system.json path')
    parser.add_argument('--account-id', default='replay')
    parser.add_argument('--magic', type=int, default=100001)
    parser.add_argument('--relative-spread', type=float, default=1.0)
    parser.add_argument('--spread-price', type=float, default=0.00010)
    parser.add_argument('--slippage-price', type=float, default=0.00002)
    parser.add_argument('--commission', type=float, default=0.0)
    parser.add_argument('--timezone', default='UTC')
    parser.add_argument('--news-file', default=None, help='Optional news calendar JSON (omit = NEWS_DATA_UNAVAILABLE)')
    parser.add_argument('--output-dir', default=None, help='Write summary JSON + trade ledger')
    parser.add_argument('--signal-audit', action='store_true', help='Also write per-bar signal audit JSONL')
    parser.add_argument('--json', action='store_true', help='Print full summary JSON')
    args = parser.parse_args(argv)
    market_path = Path(args.market).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve() if args.config else None
    news_events = _load_news_file(Path(args.news_file).expanduser().resolve() if args.news_file else None)
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else None
    execution = ReplayExecutionConfig(
        spread_price=args.spread_price,
        slippage_price=args.slippage_price,
        commission_per_trade=args.commission,
        timezone_name=args.timezone,
    )
    summary = run_replay(
        market_path=market_path,
        config_path=config_path,
        account_id=args.account_id,
        magic=args.magic,
        relative_spread=args.relative_spread,
        execution=execution,
        news_events=news_events,
        write_signal_audit=bool(args.signal_audit),
        output_dir=output_dir,
    )
    summary.pop('_simulator', None)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    else:
        print(format_summary(summary), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
