#!/usr/bin/env python3
"""Analyze live trade series (journals) and/or estimate R distribution via Monte Carlo.

Usage (Windows):
  cd C:\\Check\\System
  .venv\\Scripts\\python.exe tools\\analyze_trade_series.py
  .venv\\Scripts\\python.exe tools\\analyze_trade_series.py --root C:\\Check\\System --account 231054
"""
from __future__ import annotations
import argparse
import json
import math
import random
import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PIP = 0.0001
PIP_GBP = 0.10 / 1.27  # £ per pip @ 0.01 lot, approx
ACCOUNT_GBP = 30.0


@dataclass(frozen=True)
class ClosedTrade:
    ticket: int
    side: str
    entry: float
    exit: float
    stop_loss: float
    source: str

    @property
    def risk(self) -> float:
        return abs(self.entry - self.stop_loss)

    @property
    def pnl_price(self) -> float:
        if self.side.upper() == 'BUY':
            return self.exit - self.entry
        return self.entry - self.exit

    @property
    def r_multiple(self) -> float:
        if self.risk <= 0:
            return 0.0
        return self.pnl_price / self.risk

    @property
    def pnl_gbp(self) -> float:
        return (self.pnl_price / PIP) * PIP_GBP

    @property
    def bucket(self) -> str:
        r = self.r_multiple
        if r < 0:
            return 'bad'
        if r < 2.0:
            return 'good'
        return 'excellent'


def _parse_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _load_open_sl_from_history(history_dir: Path) -> dict[int, float]:
    """Map ticket -> initial stop_loss from archived control OPEN payloads."""
    mapping: dict[int, float] = {}
    if not history_dir.is_dir():
        return mapping
    for path in sorted(history_dir.glob('control_*.json')) + sorted(history_dir.glob('control_*.json.tmp')):
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get('action') != 'OPEN':
            continue
        ticket = payload.get('ticket')
        stop = payload.get('stop_loss')
        # ticket often arrives only in ACK; OPEN control usually has no ticket
        # store under command_id fallback via temporary key command later
        if stop is None:
            continue
        command_id = payload.get('command_id')
        if isinstance(command_id, str):
            mapping[hash(command_id) & 0x7FFFFFFF] = float(stop)  # placeholder keyed later by price match
        # also index by entry proxy: stop_loss alone used with nearest open
        mapping.setdefault(-1, float(stop))
    return mapping


def reconstruct_trades_from_journal(journal_path: Path, history_dir: Path | None=None) -> list[ClosedTrade]:
    rows = _parse_jsonl(journal_path)
    opens_by_ticket: dict[int, dict[str, Any]] = {}
    opens_by_command: dict[str, dict[str, Any]] = {}
    closes: list[dict[str, Any]] = []
    for row in rows:
        if row.get('ack_status') not in {None, 'SUCCESS', 'success'}:
            if row.get('ack_status') not in {'SUCCESS'}:
                continue
        event = row.get('event')
        if event == 'OPEN' and row.get('ack_status') == 'SUCCESS':
            ticket = row.get('ticket')
            if isinstance(ticket, int):
                opens_by_ticket[ticket] = row
            command_id = row.get('command_id')
            if isinstance(command_id, str):
                opens_by_command[command_id] = row
        elif event == 'CLOSE' and row.get('ack_status') == 'SUCCESS':
            closes.append(row)

    # build SL index from history controls matched by command_id
    sl_by_command: dict[str, float] = {}
    if history_dir is not None and history_dir.is_dir():
        for path in history_dir.glob('control*.json'):
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue
            if payload.get('action') == 'OPEN' and payload.get('stop_loss') is not None and payload.get('command_id'):
                sl_by_command[str(payload['command_id'])] = float(payload['stop_loss'])

    trades: list[ClosedTrade] = []
    for close in closes:
        ticket = close.get('ticket')
        if not isinstance(ticket, int) or ticket not in opens_by_ticket:
            continue
        open_row = opens_by_ticket[ticket]
        entry = open_row.get('price')
        exit_price = close.get('price')
        if not isinstance(exit_price, (int, float)):
            exit_price = close.get('stop_loss')
        side = open_row.get('side') or close.get('side')
        if not isinstance(entry, (int, float)) or not isinstance(exit_price, (int, float)) or not isinstance(side, str):
            continue
        stop = open_row.get('stop_loss')
        if not isinstance(stop, (int, float)):
            command_id = open_row.get('command_id')
            stop = sl_by_command.get(str(command_id)) if command_id else None
            source = 'journal+control_sl' if stop is not None else 'journal+assumed_15pip_sl'
            if stop is None:
                assumed = 15 * PIP
                stop = entry - assumed if side.upper() == 'BUY' else entry + assumed
        else:
            source = 'journal'
        trades.append(ClosedTrade(ticket=ticket, side=side.upper(), entry=float(entry), exit=float(exit_price), stop_loss=float(stop), source=source))
    return trades


@dataclass(frozen=True)
class MonteCarloConfig:
    lookback: int = 30
    structure_lookback: int = 15
    trailing_lookback: int = 5
    trailing_step_pips: float = 8.0
    stop_loss_buffer: float = 0.0002
    breakeven_progress: float = 0.25
    reward_ratio: float = 2.0
    max_bars_hold: int = 30
    ranging_extreme: float = 0.65
    block_ranging_chase: bool = True


def _gen_path(kind: str, n: int, rng: random.Random) -> list[tuple[float, float, float, float]]:
    """Return OHLC tuples. kinds: range, trend_up, trend_down, chop."""
    price = 1.1000
    bars: list[tuple[float, float, float, float]] = []
    for i in range(n):
        if kind == 'range':
            drift = 0.0
            noise = rng.gauss(0, 0.00018)
            mean_rev = (1.1000 - price) * 0.08
            move = drift + noise + mean_rev
        elif kind == 'trend_up':
            move = 0.00008 + rng.gauss(0, 0.00015)
        elif kind == 'trend_down':
            move = -0.00008 + rng.gauss(0, 0.00015)
        else:  # chop
            move = rng.choice([-1, 1]) * abs(rng.gauss(0, 0.00022))
        open_ = price
        close = price + move
        wick = abs(rng.gauss(0, 0.00012))
        high = max(open_, close) + wick
        low = min(open_, close) - wick
        bars.append((open_, high, low, close))
        price = close
    return bars


def _structure_swing(bars: list[tuple[float, float, float, float]], lookback: int) -> tuple[float, float]:
    window = bars[-lookback:] if len(bars) > lookback else bars
    return (max(b[1] for b in window), min(b[2] for b in window))


def _simulate_one(kind: str, rng: random.Random, cfg: MonteCarloConfig) -> ClosedTrade | None:
    bars = _gen_path(kind, cfg.lookback + cfg.max_bars_hold + 5, rng)
    warmup = bars[:cfg.lookback]
    swing_high, swing_low = _structure_swing(warmup, cfg.structure_lookback)
    range_height = swing_high - swing_low
    if range_height <= 0:
        return None
    close = warmup[-1][3]
    range_pos = (close - swing_low) / range_height
    recent = warmup[-3:]
    recent_delta = recent[-1][3] - recent[0][3]

    # crude direction: prefer sell near top with down micro-move, buy near bottom with up micro-move
    side: str | None = None
    if cfg.block_ranging_chase and kind in {'range', 'chop'}:
        if range_pos > cfg.ranging_extreme and recent_delta < 0:
            side = 'SELL'
        elif range_pos < (1.0 - cfg.ranging_extreme) and recent_delta > 0:
            side = 'BUY'
        else:
            return None
    else:
        side = 'BUY' if recent_delta >= 0 else 'SELL'

    entry = close
    if side == 'BUY':
        stop = swing_low - cfg.stop_loss_buffer
        if stop >= entry:
            return None
        ref_tp = entry + (entry - stop) * cfg.reward_ratio
    else:
        stop = swing_high + cfg.stop_loss_buffer
        if stop <= entry:
            return None
        ref_tp = entry - (stop - entry) * cfg.reward_ratio
    risk = abs(entry - stop)
    if risk <= 0 or risk > 25 * PIP:
        return None

    trail_dist = cfg.trailing_step_pips * PIP
    held = warmup[:]
    current_sl = stop
    for i in range(cfg.max_bars_hold):
        bar = bars[cfg.lookback + i]
        held.append(bar)
        o, h, l, c = bar
        # trail / BE update on closed bar
        t_high, t_low = _structure_swing(held, cfg.trailing_lookback)
        if side == 'BUY':
            candidates = [t_low - cfg.stop_loss_buffer, c - trail_dist]
            progress = (c - entry) / (ref_tp - entry) if ref_tp > entry else 0.0
            if progress >= cfg.breakeven_progress and current_sl < entry:
                candidates.append(entry)
            candidate = max(candidates)
            if candidate > current_sl and candidate < c:
                current_sl = candidate
            if l <= current_sl:
                return ClosedTrade(ticket=i, side=side, entry=entry, exit=current_sl, stop_loss=stop, source=f'mc:{kind}')
        else:
            candidates = [t_high + cfg.stop_loss_buffer, c + trail_dist]
            progress = (entry - c) / (entry - ref_tp) if entry > ref_tp else 0.0
            if progress >= cfg.breakeven_progress and current_sl > entry:
                candidates.append(entry)
            candidate = min(candidates)
            if candidate < current_sl and candidate > c:
                current_sl = candidate
            if h >= current_sl:
                return ClosedTrade(ticket=i, side=side, entry=entry, exit=current_sl, stop_loss=stop, source=f'mc:{kind}')
    # time stop: exit at last close (management would not CLOSE with allow_close=false — model SL still in market)
    last = held[-1][3]
    return ClosedTrade(ticket=999, side=side, entry=entry, exit=last, stop_loss=stop, source=f'mc:{kind}:time')


def run_monte_carlo(n: int=400, seed: int=42) -> list[ClosedTrade]:
    rng = random.Random(seed)
    cfg = MonteCarloConfig()
    kinds = ['range', 'range', 'chop', 'trend_up', 'trend_down']
    out: list[ClosedTrade] = []
    attempts = 0
    while len(out) < n and attempts < n * 20:
        attempts += 1
        kind = rng.choice(kinds)
        trade = _simulate_one(kind, rng, cfg)
        if trade is not None:
            out.append(trade)
    return out


def summarize(trades: list[ClosedTrade], *, title: str) -> dict[str, Any]:
    if not trades:
        return {'title': title, 'count': 0}
    buckets = Counter(t.bucket for t in trades)
    rs = [t.r_multiple for t in trades]
    by_bucket_r = {
        'bad': [t.r_multiple for t in trades if t.bucket == 'bad'],
        'good': [t.r_multiple for t in trades if t.bucket == 'good'],
        'excellent': [t.r_multiple for t in trades if t.bucket == 'excellent'],
    }
    avg = {k: (statistics.fmean(v) if v else 0.0) for k, v in by_bucket_r.items()}
    total = len(trades)
    mix = {k: buckets.get(k, 0) / total for k in ('bad', 'good', 'excellent')}
    # scale to 10-trade series equivalent expected R
    expected_r_per_trade = statistics.fmean(rs)
    series_10_r = expected_r_per_trade * 10
    # classic 5/3/2 using observed averages
    classic_r = 5 * avg['bad'] + 3 * avg['good'] + 2 * avg['excellent']
    # or using observed mix proportions * 10
    mix_series_r = 10 * (mix['bad'] * avg['bad'] + mix['good'] * avg['good'] + mix['excellent'] * avg['excellent'])

    # match scenario by overall expectancy + excellence rate (not forced 5/3/2 counts)
    if expected_r_per_trade >= 0.5 and mix['excellent'] >= 0.25 and avg['excellent'] >= 2.5:
        scenario = 'C_strong_trail'
    elif expected_r_per_trade >= 0.25 and mix['excellent'] >= 0.15 and avg['excellent'] >= 2.0:
        scenario = 'B_target_2R'
    elif expected_r_per_trade >= 0.05 and avg['good'] >= 0.5:
        scenario = 'A_conservative'
    elif expected_r_per_trade >= 0.0:
        scenario = 'A_weak_positive'
    else:
        scenario = 'D_reality_chop'

    return {
        'title': title,
        'count': total,
        'mix': mix,
        'avg_r': avg,
        'mean_r': expected_r_per_trade,
        'median_r': statistics.median(rs),
        'series_10_expected_r': series_10_r,
        'classic_5_3_2_r_using_avg': classic_r,
        'mix_scaled_10_r': mix_series_r,
        'scenario': scenario,
        'win_rate': sum(1 for r in rs if r > 0) / total,
        'mean_sl_pips': statistics.fmean(abs(t.entry - t.stop_loss) / PIP for t in trades),
        'mean_pnl_gbp_001': statistics.fmean(t.pnl_gbp for t in trades),
    }


def print_summary(summary: dict[str, Any]) -> None:
    print()
    print('=' * 64)
    print(summary.get('title', 'summary'))
    print('=' * 64)
    if summary.get('count', 0) == 0:
        print('Nav datu.')
        return
    mix = summary['mix']
    avg = summary['avg_r']
    print(f"Trades: {summary['count']}")
    print(f"Sadalījums: bad={mix['bad']*100:.1f}%  good={mix['good']*100:.1f}%  excellent={mix['excellent']*100:.1f}%")
    print(f"Vidējais R: bad={avg['bad']:+.2f}  good={avg['good']:+.2f}  excellent={avg['excellent']:+.2f}")
    print(f"Kopā mean R/trade={summary['mean_r']:+.3f}  median={summary['median_r']:+.3f}  win_rate={summary['win_rate']*100:.1f}%")
    print(f"Vidējais SL ≈ {summary['mean_sl_pips']:.1f} pip")
    print(f"10-trade expected ≈ {summary['series_10_expected_r']:+.2f}R  (~£{summary['series_10_expected_r'] * summary['mean_sl_pips'] * PIP_GBP:+.2f} pie vidējā SL)")
    print(f"Ja piespiedu 5/3/2 ar TAVĀM avg R → {summary['classic_5_3_2_r_using_avg']:+.2f}R")
    print(f"Scenārija matches: {summary['scenario']}")
    print(f"Mean PnL/trade @0.01 ≈ £{summary['mean_pnl_gbp_001']:+.3f}  |  £30 kontam ~{summary['mean_pnl_gbp_001']/ACCOUNT_GBP*100:+.2f}% / trade")


def find_journals(root: Path, account: str | None) -> list[tuple[Path, Path | None]]:
    clients = root / 'data' / 'clients'
    if not clients.is_dir():
        return []
    found: list[tuple[Path, Path | None]] = []
    for account_dir in clients.iterdir():
        if not account_dir.is_dir():
            continue
        if account and account_dir.name != account:
            continue
        journal_dir = account_dir / 'journal'
        if not journal_dir.is_dir():
            continue
        for journal in journal_dir.glob('trade_*.jsonl'):
            # history path: data/history/{account}/{symbol}/{magic}/ or clients history
            history = None
            parts = journal.stem.split('_')  # trade_EURUSD_100001
            if len(parts) >= 3:
                symbol, magic = parts[1], parts[2]
                cand = root / 'data' / 'history' / account_dir.name / symbol / magic
                if cand.is_dir():
                    history = cand
            found.append((journal, history))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description='Analyze live R distribution / Monte Carlo estimate')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--account', type=str, default=None)
    parser.add_argument('--monte-carlo', type=int, default=400, help='simulated closed trades if journals empty')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    print(f'Root: {args.root}')
    journal_sets = find_journals(args.root, args.account)
    live_trades: list[ClosedTrade] = []
    for journal_path, history_dir in journal_sets:
        trades = reconstruct_trades_from_journal(journal_path, history_dir)
        print(f'Journal {journal_path}: {len(trades)} closed round-trips')
        live_trades.extend(trades)

    if live_trades:
        print_summary(summarize(live_trades, title='LIVE journal reconstrution'))
    else:
        print('LIVE journali: nav atrasti closed round-trips (OPEN+CLOSE SUCCESS).')
        print('Tas ir normāli, ja vēl nav datu vai CLOSE neverāk journal (SL hit pie brokera bez external CLOSE ieraksta).')

    mc = run_monte_carlo(n=args.monte_carlo, seed=args.seed)
    print_summary(summarize(mc, title=f'Monte Carlo (live-like config, n={len(mc)})'))
    print()
    print('Piezīme: Monte Carlo ir empirisks modelis ar range/chop/trend mix,')
    print('nevis tavi īstie live darījumi. Palaid šo pašu komandu uz C:\\Check\\System pēc datiem.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
