from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from checktrader.bridge.atomic_files import read_json
from checktrader.domain.enums import ReasonCode, Side, StrategyType
from checktrader.domain.models import AccountStatus, Acknowledgement, Candle, MarketSnapshot, Position

logger = logging.getLogger(__name__)


def _payload(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if data is None:
        return None
    p = data.get("payload", data)
    return p if isinstance(p, dict) else None


def _read_latest_or_glob(subdir: Path, *, role: str = "market") -> dict[str, Any] | None:
    """Prefer latest.json; then v3 *_{role}.json; avoid legacy {role}_* when newer v3 exists."""
    latest = subdir / "latest.json"
    if latest.exists():
        data = read_json(latest)
        if data is not None:
            return data

    if not subdir.exists():
        return None

    files = [p for p in subdir.glob("*.json") if p.is_file()]

    def score(path: Path) -> tuple[int, float]:
        name = path.name.lower()
        if name.endswith(f"_{role}.json"):
            tier = 2
        elif name.startswith(f"{role}_"):
            tier = 0
        else:
            tier = 1
        return (tier, path.stat().st_mtime)

    for candidate in sorted(files, key=score, reverse=True):
        data = read_json(candidate)
        if data is not None:
            return data
    return None


def _raw_m1_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("bars_m1")
    if raw is None:
        candles = payload.get("candles")
        if isinstance(candles, dict):
            raw = candles.get("M1")
        elif isinstance(candles, list):
            raw = candles
    if raw is None:
        raw = payload.get("m1", [])
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict)]


def _parse_m1_bars(rows: list[dict[str, Any]]) -> list[Candle]:
    out: list[Candle] = []
    skipped = 0
    for row in rows:
        try:
            out.append(Candle.from_dict({**row, "closed": True}, "M1"))
        except (ValueError, KeyError, TypeError) as exc:
            skipped += 1
            if skipped <= 3:
                logger.warning("skipping invalid M1 bar (%s): %s", exc, row)
    if skipped:
        logger.warning("skipped %s invalid M1 bars; kept %s", skipped, len(out))
    return out


def read_market(bridge_dir: Path, default_symbol: str) -> MarketSnapshot | None:
    """Read market snapshot from bridge_dir/market/latest.json (or glob fallback)."""
    p = _payload(_read_latest_or_glob(bridge_dir / "market", role="market"))
    if p is None:
        return None

    ts = p.get("timestamp") or p.get("time") or p.get("generated_at_utc")
    t = datetime.fromisoformat(str(ts).replace("Z", "+00:00")) if ts else datetime.now(UTC)
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)

    bid = float(p.get("bid", p.get("close", 0.0)))
    ask = float(p.get("ask", bid))
    symbol = str(p.get("symbol", default_symbol))
    m1_bars = _parse_m1_bars(_raw_m1_rows(p))
    meta: dict[str, Any] = {}
    for key in (
        "digits",
        "point",
        "tick_size",
        "tick_value",
        "stop_level",
        "freeze_level",
        "min_lot",
        "max_lot",
        "lot_step",
        "account_number",
        "magic_number",
    ):
        if key in p and p[key] is not None:
            meta[key] = p[key]

    return MarketSnapshot(
        symbol,
        bid,
        ask,
        t,
        m1_bars,
        [],  # M5/M15 are aggregated internally from M1
        [],
        heartbeat_at=t,
        meta=meta,
    )


def read_status(bridge_dir: Path) -> AccountStatus | None:
    """Read account status from bridge_dir/status/latest.json."""
    p = _payload(_read_latest_or_glob(bridge_dir / "status", role="status"))
    if p is None:
        return None

    # MT4 field names: account_number, balance, equity, free_margin, trade_allowed
    account_id = str(p.get("account_number") or p.get("account_id") or p.get("login", ""))
    balance = float(p.get("balance", 0.0))
    equity = float(p.get("equity", balance))
    margin_free = float(p.get("free_margin") or p.get("margin_free", 0.0))
    currency = str(p.get("currency", "USD"))
    trading_allowed = bool(p.get("trade_allowed", p.get("trading_allowed", True)))
    connected = bool(p.get("connected", True))
    return AccountStatus(
        account_id,
        balance,
        equity,
        margin_free,
        currency,
        trading_allowed,
        connected,
    )


def read_positions(bridge_dir: Path) -> list[Position]:
    """Read positions from bridge_dir/status/latest.json (MT4 includes them in status)."""
    p = _payload(_read_latest_or_glob(bridge_dir / "status", role="status"))
    # Fall back to a dedicated positions.json if status lacks them
    if p is None or "positions" not in p:
        p2 = _payload(read_json(bridge_dir / "positions.json"))
        if p2 is not None:
            p = p2
    rows = [] if p is None else p.get("positions", [])
    out: list[Position] = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        opened = r.get("opened_at") or r.get("open_time")
        opened_at = datetime.fromisoformat(str(opened).replace("Z", "+00:00")) if opened else datetime.now(UTC)
        if opened_at.tzinfo is None:
            opened_at = opened_at.replace(tzinfo=UTC)
        side = Side.SELL if str(r.get("side", "BUY")).upper() in {"SHORT", "SELL"} else Side.BUY
        lot_raw = r.get("lot", r.get("lots", 0.0))
        entry_raw = r.get("entry_price", r.get("open_price", 0.0))
        lot = float(lot_raw if lot_raw is not None else 0.0)
        entry = float(entry_raw if entry_raw is not None else 0.0)
        out.append(
            Position(
                str(r.get("position_id", r.get("ticket", ""))),
                str(r.get("symbol", "")),
                side,
                lot,
                entry,
                float(r["stop_loss"]) if r.get("stop_loss") is not None else None,
                float(r["take_profit"]) if r.get("take_profit") is not None else None,
                opened_at,
                StrategyType(r.get("strategy", "TREND_CONTINUATION")),
                float(r["current_price"]) if r.get("current_price") is not None else None,
                float(r.get("profit", 0.0) or 0.0),
                int(r["magic_number"]) if r.get("magic_number") is not None else None,
            )
        )
    return out


def read_acks(bridge_dir: Path) -> list[Acknowledgement]:
    """Read ACKs from bridge_dir/acknowledgements/*.json (one file per ACK)."""
    ack_dir = bridge_dir / "acknowledgements"
    if not ack_dir.is_dir():
        return []
    out: list[Acknowledgement] = []
    for ack_file in ack_dir.glob("*.json"):
        if ack_file.name.startswith("."):
            continue
        data = read_json(ack_file)
        if data is None:
            continue
        p = data.get("payload", data)
        if not isinstance(p, dict):
            continue
        accepted = bool(p.get("accepted", False))
        default = "ACK_ACCEPTED" if accepted else "ACK_REJECTED"
        try:
            out.append(
                Acknowledgement(
                    str(p.get("command_id", "")),
                    accepted,
                    ReasonCode(p.get("reason", default)),
                    str(p["broker_order_id"]) if p.get("broker_order_id") is not None else None,
                    str(p.get("message", "")),
                    payload=p,
                )
            )
        except (ValueError, KeyError):
            continue
    return out
