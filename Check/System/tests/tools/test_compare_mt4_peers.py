from __future__ import annotations

from tools.compare_mt4_peers import (
    DIMENSIONS,
    PEERS,
    build_report,
    format_text,
    head_to_head,
    max_possible,
    rank_peers,
    total_score,
)


def test_all_peers_have_every_dimension() -> None:
    for peer in PEERS:
        assert set(peer.scores) == set(DIMENSIONS)
        assert all(0 <= peer.scores[d] <= 5 for d in DIMENSIONS)


def test_check_ranks_first_on_capability() -> None:
    ranked = rank_peers()
    assert ranked[0]['id'] == 'check_system'
    assert ranked[0]['total'] == total_score(next(p for p in PEERS if p.id == 'check_system'))
    assert ranked[0]['max'] == max_possible()


def test_all_peers_are_mt4_oriented() -> None:
    for peer in PEERS:
        assert 'MT4' in peer.mt4_only_note or 'mt4' in peer.mt4_only_note.lower() or 'mql4' in peer.mt4_only_note.lower()


def test_head_to_head_positive_vs_bridges() -> None:
    rows = {row['vs']: row for row in head_to_head()}
    assert rows['dwx_connect_mt4']['delta'] > 0
    assert rows['otmql4py']['delta'] > 0
    assert rows['mt4_connector_json']['wins'] >= 8


def test_report_text_contains_ranking() -> None:
    text = format_text(build_report())
    assert 'MT4 PEER SALIDZINAJUMS' in text
    assert 'Check/System' in text
    assert 'DWX Connect' in text
    assert 'VERDIKTS' in text
