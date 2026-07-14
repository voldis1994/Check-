#!/usr/bin/env python3
"""Compare Check/System against the best available MT4-only public peers.

Scores are capability ratings (0-5), not live PnL. Peers are filtered to
projects that include a real MetaTrader 4 EA / MT4 execution path.

Usage (Windows):
  cd C:\\Check\\System
  .venv\\Scripts\\python.exe tools\\compare_mt4_peers.py
  SALIDZINI_MT4.bat
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Capability ratings: 0 = absent, 5 = reference / best-in-class for that axis.
DIMENSIONS: tuple[str, ...] = (
    'mt4_native',
    'bridge_protocol',
    'built_in_strategy',
    'dual_buy_sell_score',
    'entry_gates',
    'trade_management',
    'risk_controls',
    'instance_isolation',
    'journals_ops',
    'ai_advisory',
    'automated_tests',
    'community_maturity',
)

DIMENSION_LV: dict[str, str] = {
    'mt4_native': 'MT4 nativais EA / izpilde',
    'bridge_protocol': 'Python↔MT4 protokols',
    'built_in_strategy': 'Iebūvēta stratēģija / lēmumu stack',
    'dual_buy_sell_score': 'BUY un SELL abu score',
    'entry_gates': 'Ieejas filtri (closed-bar, chase, u.c.)',
    'trade_management': 'Trailing / struktūras izejas',
    'risk_controls': 'Risks / sizing / bloķēšana',
    'instance_isolation': 'Account+Symbol+Magic izolācija',
    'journals_ops': 'Žurnāli / recovery / ops',
    'ai_advisory': 'AI advisory / veto slānis',
    'automated_tests': 'Automātiskie testi',
    'community_maturity': 'Kopiena / uzturēšana / docs',
}


@dataclass(frozen=True)
class Peer:
    id: str
    name: str
    url: str
    mt4_only_note: str
    why_included: str
    scores: dict[str, int]
    notes: tuple[str, ...]


# Best publicly available MT4 peers (researched). No MT5-only stacks.
PEERS: tuple[Peer, ...] = (
    Peer(
        id='check_system',
        name='Check/System (šī sistēma)',
        url='local',
        mt4_only_note='mql4/ Experts + file protocol',
        why_included='Mērķa sistēma',
        scores={
            'mt4_native': 5,
            'bridge_protocol': 5,
            'built_in_strategy': 5,
            'dual_buy_sell_score': 5,
            'entry_gates': 5,
            'trade_management': 5,
            'risk_controls': 4,
            'instance_isolation': 5,
            'journals_ops': 5,
            'ai_advisory': 4,
            'automated_tests': 5,
            'community_maturity': 2,
        },
        notes=(
            'File protocol + ACK + atomic control.',
            'M1 structure + dual scoring + WAIT/BLOCK.',
            'Closed-bar gate + ranging chase filter.',
            'Trail-only exits (bez fiksēta broker TP).',
            'AI advisory; pytest suite ~900+.',
        ),
    ),
    Peer(
        id='dwx_connect_mt4',
        name='Darwinex DWX Connect (MT4)',
        url='https://github.com/darwinex/dwxconnect',
        mt4_only_note='dwx_server_mt4.mq4 (MT4 EA); arī MT5 variants — šeit vērtējam MT4 ceļu',
        why_included='Labākais publiskais Python↔MT4 file-bridge standarts (~227★)',
        scores={
            'mt4_native': 5,
            'bridge_protocol': 5,
            'built_in_strategy': 1,
            'dual_buy_sell_score': 0,
            'entry_gates': 0,
            'trade_management': 1,
            'risk_controls': 2,
            'instance_isolation': 2,
            'journals_ops': 2,
            'ai_advisory': 0,
            'automated_tests': 1,
            'community_maturity': 5,
        },
        notes=(
            'Zelta standarts bridge API: tick/bar + orders via Files.',
            'Stratēģiju tu raksti pats — EA ir serveris, ne brain.',
            'Nav built-in structure scorer / ranging chase.',
            'Nav ACK+instance izolācijas kā Check līgumā.',
        ),
    ),
    Peer(
        id='anubhav_mt4_bot',
        name='Anu-bhav mt4_trading_bot',
        url='https://github.com/Anu-bhav/mt4_trading_bot',
        mt4_only_note='Enhanced DWX_server_MT4.mq4 + Python framework',
        why_included='Labākais “pilnais” DWX-based MT4+Python bot framework (risk + strategy hooks)',
        scores={
            'mt4_native': 5,
            'bridge_protocol': 4,
            'built_in_strategy': 3,
            'dual_buy_sell_score': 1,
            'entry_gates': 1,
            'trade_management': 2,
            'risk_controls': 3,
            'instance_isolation': 2,
            'journals_ops': 3,
            'ai_advisory': 0,
            'automated_tests': 1,
            'community_maturity': 2,
        },
        notes=(
            'DWX Connect paplašinājums: heartbeat, risk config, strategy params.',
            'Produkcijas bot framework, bet ne specialization M1 structure stack.',
            'Mazāks community nekā Darwinex oriģinālam.',
        ),
    ),
    Peer(
        id='otmql4zmq',
        name='OpenTrading OTMql4Zmq',
        url='https://github.com/OpenTrading/OTMql4Zmq',
        mt4_only_note='MT4 ZeroMQ bridge (tikai MT4)',
        why_included='Spēcīgākais open-source MT4 ZMQ bridge (~100★)',
        scores={
            'mt4_native': 5,
            'bridge_protocol': 4,
            'built_in_strategy': 1,
            'dual_buy_sell_score': 0,
            'entry_gates': 0,
            'trade_management': 1,
            'risk_controls': 1,
            'instance_isolation': 1,
            'journals_ops': 1,
            'ai_advisory': 0,
            'automated_tests': 1,
            'community_maturity': 4,
        },
        notes=(
            'ZMQ transport — ātrāks par failiem, bet DLL/deps.',
            'Bridge layer, ne gatekeeper decision engine.',
            'Legacy-leaning uzturēšana; labs references protokols.',
        ),
    ),
    Peer(
        id='otmql4py',
        name='OpenTrading OTMql4Py',
        url='https://github.com/OpenTrading/OTMql4Py',
        mt4_only_note='Embed Python interpreter inside MT4 (Python 2.7 only)',
        why_included='Klasiskais “Python iekšā MT4” (~108★); unikāla MT4-only arhitektūra',
        scores={
            'mt4_native': 5,
            'bridge_protocol': 3,
            'built_in_strategy': 1,
            'dual_buy_sell_score': 0,
            'entry_gates': 0,
            'trade_management': 1,
            'risk_controls': 1,
            'instance_isolation': 1,
            'journals_ops': 1,
            'ai_advisory': 0,
            'automated_tests': 1,
            'community_maturity': 3,
        },
        notes=(
            'Python 2.7 + 32-bit — leģendārs, bet novecojis production stack.',
            'Nav failu protokola; polling no EA uz Python.',
            'Nav moderno AI/advisory un pytest slāņu.',
        ),
    ),
    Peer(
        id='mt4_connector_json',
        name='michael-abdo/mt4-connector',
        url='https://github.com/michael-abdo/mt4-connector',
        mt4_only_note='MT4 Manager API + JSON signal file (MT4 server path)',
        why_included='Vieglākais modernais JSON signal→MT4 ceļš',
        scores={
            'mt4_native': 4,
            'bridge_protocol': 2,
            'built_in_strategy': 0,
            'dual_buy_sell_score': 0,
            'entry_gates': 0,
            'trade_management': 2,
            'risk_controls': 1,
            'instance_isolation': 1,
            'journals_ops': 1,
            'ai_advisory': 0,
            'automated_tests': 0,
            'community_maturity': 1,
        },
        notes=(
            'Signal writer / Manager API — vairāk executor nekā analysis stack.',
            'Neder kā Check analogs decision+journal+instance modelī.',
        ),
    ),
)


def _validate_peer(peer: Peer) -> None:
    missing = [d for d in DIMENSIONS if d not in peer.scores]
    extra = [k for k in peer.scores if k not in DIMENSIONS]
    if missing or extra:
        raise ValueError(f'{peer.id}: missing={missing} extra={extra}')
    for key, value in peer.scores.items():
        if not isinstance(value, int) or value < 0 or value > 5:
            raise ValueError(f'{peer.id}.{key}={value} out of 0..5')


def total_score(peer: Peer) -> int:
    return sum(peer.scores[d] for d in DIMENSIONS)


def max_possible() -> int:
    return 5 * len(DIMENSIONS)


def rank_peers(peers: tuple[Peer, ...] = PEERS) -> list[dict[str, Any]]:
    for peer in peers:
        _validate_peer(peer)
    ranked = sorted(peers, key=total_score, reverse=True)
    rows: list[dict[str, Any]] = []
    for index, peer in enumerate(ranked, start=1):
        total = total_score(peer)
        rows.append(
            {
                'rank': index,
                'id': peer.id,
                'name': peer.name,
                'url': peer.url,
                'mt4_only_note': peer.mt4_only_note,
                'why_included': peer.why_included,
                'total': total,
                'max': max_possible(),
                'pct': round(100.0 * total / max_possible(), 1),
                'scores': dict(peer.scores),
                'notes': list(peer.notes),
            }
        )
    return rows


def dimension_winners(peers: tuple[Peer, ...] = PEERS) -> dict[str, list[str]]:
    winners: dict[str, list[str]] = {}
    for dim in DIMENSIONS:
        best = max(peer.scores[dim] for peer in peers)
        winners[dim] = [peer.id for peer in peers if peer.scores[dim] == best]
    return winners


def head_to_head(ours_id: str = 'check_system', peers: tuple[Peer, ...] = PEERS) -> list[dict[str, Any]]:
    ours = next(p for p in peers if p.id == ours_id)
    rows: list[dict[str, Any]] = []
    for peer in peers:
        if peer.id == ours_id:
            continue
        wins = sum(1 for d in DIMENSIONS if ours.scores[d] > peer.scores[d])
        ties = sum(1 for d in DIMENSIONS if ours.scores[d] == peer.scores[d])
        losses = sum(1 for d in DIMENSIONS if ours.scores[d] < peer.scores[d])
        rows.append(
            {
                'vs': peer.id,
                'vs_name': peer.name,
                'wins': wins,
                'ties': ties,
                'losses': losses,
                'our_total': total_score(ours),
                'their_total': total_score(peer),
                'delta': total_score(ours) - total_score(peer),
            }
        )
    rows.sort(key=lambda r: r['delta'], reverse=True)
    return rows


def build_report(peers: tuple[Peer, ...] = PEERS) -> dict[str, Any]:
    ranked = rank_peers(peers)
    ours = next(r for r in ranked if r['id'] == 'check_system')
    return {
        'generated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'scope': 'MT4-only public peers (best available file/ZMQ/embed bridges)',
        'excluded': [
            'MT5-only MetaTrader5 Python package',
            'Commercial black-box MQL Market EAs without open protocol',
            'Generic TradingView Pine indicators (nav MT4 izpilde)',
        ],
        'dimensions': list(DIMENSIONS),
        'dimension_labels_lv': dict(DIMENSION_LV),
        'ranking': ranked,
        'check_rank': ours['rank'],
        'check_total': ours['total'],
        'check_pct': ours['pct'],
        'dimension_winners': dimension_winners(peers),
        'head_to_head': head_to_head(peers=peers),
        'verdict_lv': _verdict_lv(ours, ranked),
    }


def _verdict_lv(ours: dict[str, Any], ranked: list[dict[str, Any]]) -> list[str]:
    top_external = next(r for r in ranked if r['id'] != 'check_system')
    return [
        f"Check/System = #{ours['rank']} / {len(ranked)} (kopā {ours['total']}/{ours['max']}, {ours['pct']}%).",
        f"Tuvākais ārējais: {top_external['name']} ({top_external['total']}/{top_external['max']}).",
        'Bridge: DWX Connect MT4 ir references API; Check ir tālāk strategy+gates+journals ziņā.',
        'Anu-bhav ir labākais “pilnais bot framework” uz DWX; tomēr bez dual score / ranging chase / trail-only stack.',
        'OTMql4Zmq/OTMql4Py = spēcīgi MT4 bridge/legacy, ne moderns M1 decision engine.',
        'Šis nav PnL backtest pret peeriem — tas ir capability score pret labākajiem MT4 publiskajiem līdziniekiem.',
    ]


def format_text(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append('=== MT4 PEER SALIDZINAJUMS ===')
    lines.append(f"Generated: {report['generated_utc']}")
    lines.append(f"Scope: {report['scope']}")
    lines.append('')
    lines.append('--- RANKING (capability 0-5 x dimensions) ---')
    for row in report['ranking']:
        marker = ' <<' if row['id'] == 'check_system' else ''
        lines.append(
            f"#{row['rank']}  {row['total']:>2}/{row['max']} ({row['pct']:>5.1f}%)  {row['name']}{marker}"
        )
        lines.append(f"     {row['url']}")
        lines.append(f"     MT4: {row['mt4_only_note']}")
    lines.append('')
    lines.append('--- HEAD-TO-HEAD (Check vs katru) ---')
    for row in report['head_to_head']:
        lines.append(
            f"vs {row['vs_name']}: W{row['wins']} T{row['ties']} L{row['losses']}  "
            f"delta={row['delta']:+d} ({row['our_total']} vs {row['their_total']})"
        )
    lines.append('')
    lines.append('--- DIMENSIJU DETAĻAS (Check) ---')
    check = next(r for r in report['ranking'] if r['id'] == 'check_system')
    for dim in report['dimensions']:
        label = report['dimension_labels_lv'][dim]
        winners = ', '.join(report['dimension_winners'][dim])
        lines.append(f"  {check['scores'][dim]}/5  {label}  [best: {winners}]")
    lines.append('')
    lines.append('--- VERDIKTS ---')
    for line in report['verdict_lv']:
        lines.append(f'* {line}')
    lines.append('')
    lines.append('--- PEER NOTES ---')
    for row in report['ranking']:
        lines.append(f"{row['name']}:")
        for note in row['notes']:
            lines.append(f'  - {note}')
    lines.append('')
    return '\n'.join(lines)


def write_outputs(report: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    json_path = out_dir / f'mt4_peer_compare_{stamp}.json'
    txt_path = out_dir / f'mt4_peer_compare_{stamp}.txt'
    latest_json = out_dir / 'mt4_peer_compare_latest.json'
    latest_txt = out_dir / 'mt4_peer_compare_latest.txt'
    text = format_text(report)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    json_path.write_text(payload + '\n', encoding='utf-8')
    txt_path.write_text(text, encoding='utf-8')
    latest_json.write_text(payload + '\n', encoding='utf-8')
    latest_txt.write_text(text, encoding='utf-8')
    return latest_txt, latest_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Compare Check/System to best MT4-only peers')
    parser.add_argument('--root', type=Path, default=None, help='System root (default: auto)')
    parser.add_argument('--json-only', action='store_true', help='Print JSON instead of text')
    args = parser.parse_args(argv)

    root = args.root
    if root is None:
        root = Path(__file__).resolve().parents[1]
    out_dir = root / 'data' / 'reports'

    report = build_report()
    latest_txt, latest_json = write_outputs(report, out_dir)

    if args.json_only:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_text(report))
        print(f'Wrote: {latest_txt}')
        print(f'Wrote: {latest_json}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
