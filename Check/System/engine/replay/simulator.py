"""Stateful replay simulator with position lifecycle and metrics."""
from __future__ import annotations
import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from engine.core.clock import format_utc_timestamp
from engine.core.config import load_system_config
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.decision.engine import run_decision_engine
from engine.normalizer.market_normalizer import NormalizedMarketBar, normalize_market_csv
from engine.protocol.constants import Decision, Side, TradeOutcome
from engine.protocol.models import SystemConfig
from engine.replay.context import build_replay_universe
from engine.replay.execution_model import ReplayExecutionConfig, default_replay_execution_config
from engine.state.instance_state import InstanceState

PositionState = str  # FLAT | PENDING_ENTRY | OPEN | CLOSED


@dataclass
class PendingEntry:
    side: str
    signal_bar_utc: str
    signal_time_utc: str
    entry_price_hint: float
    stop_loss: float
    take_profit: float
    fingerprint: str | None
    setup_type: str | None
    buy_score: float
    sell_score: float
    score_delta: float
    market_quality: float
    confirmation_count: int
    reason: str
    session: str
    regime: str
    signal_snapshot: dict[str, Any]


@dataclass
class OpenPosition:
    trade_id: str
    side: str
    fingerprint: str | None
    setup_type: str | None
    signal_time_utc: str
    entry_time_utc: str
    entry_price: float
    stop_loss: float
    take_profit: float
    spread: float
    slippage: float
    commission: float
    buy_score: float
    sell_score: float
    score_delta: float
    market_quality: float
    confirmation_count: int
    session: str
    regime: str
    bars_open: int = 0
    mfe: float = 0.0
    mae: float = 0.0
    signal_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClosedTrade:
    trade_id: str
    fingerprint: str | None
    symbol: str
    timeframe: str
    side: str
    setup_type: str | None
    signal_time: str
    entry_time: str
    entry_price: float
    stop_loss: float
    take_profit: float
    exit_time: str
    exit_price: float
    exit_reason: str
    outcome: str
    spread: float
    slippage: float
    commission: float
    gross_result: float
    net_result: float
    result_r: float
    mfe: float
    mae: float
    buy_score: float
    sell_score: float
    score_delta: float
    market_quality: float
    confirmation_count: int
    session: str
    regime: str
    duration_bars: int


def _apply_entry_costs(*, side: str, raw_open: float, spread: float, slippage: float) -> float:
    half_spread = spread / 2.0
    if side == Side.BUY.value:
        return raw_open + half_spread + slippage
    return raw_open - half_spread - slippage


def _gross_pnl(*, side: str, entry: float, exit_price: float, lot_size: float, point_value_per_lot: float, point: float) -> float:
    if point <= 0:
        point = 1e-5
    if side == Side.BUY.value:
        points = (exit_price - entry) / point
    else:
        points = (entry - exit_price) / point
    return points * point_value_per_lot * lot_size


def _r_multiple(*, side: str, entry: float, exit_price: float, stop_loss: float) -> float:
    risk = abs(entry - stop_loss)
    if risk <= 0:
        return 0.0
    if side == Side.BUY.value:
        return (exit_price - entry) / risk
    return (entry - exit_price) / risk


def _outcome_from_r(result_r: float, *, breakeven_eps: float = 1e-9) -> str:
    if result_r > breakeven_eps:
        return TradeOutcome.WIN.value
    if result_r < -breakeven_eps:
        return TradeOutcome.LOSS.value
    return TradeOutcome.BREAKEVEN.value


def _resolve_intrabar_exit(
    *,
    side: str,
    bar: NormalizedMarketBar,
    stop_loss: float,
    take_profit: float,
    conflict_rule: str,
) -> tuple[str, float] | None:
    hit_sl = bar.low <= stop_loss <= bar.high if side == Side.BUY.value else bar.low <= stop_loss <= bar.high
    hit_tp = bar.low <= take_profit <= bar.high if side == Side.BUY.value else bar.low <= take_profit <= bar.high
    # Distance checks (SL/TP may lie outside if gap — still check through extremes)
    if side == Side.BUY.value:
        hit_sl = bar.low <= stop_loss
        hit_tp = bar.high >= take_profit
    else:
        hit_sl = bar.high >= stop_loss
        hit_tp = bar.low <= take_profit
    if hit_sl and hit_tp:
        # Default worst-case: SL wins for the trader.
        if conflict_rule == 'worst_case':
            return ('SL_TP_CONFLICT_WORST', stop_loss)
        return ('TP_SL_CONFLICT_BEST', take_profit)
    if hit_sl:
        return ('SL', stop_loss)
    if hit_tp:
        return ('TP', take_profit)
    return None


def _update_excursion(*, position: OpenPosition, bar: NormalizedMarketBar) -> None:
    if position.side == Side.BUY.value:
        favorable = bar.high - position.entry_price
        adverse = position.entry_price - bar.low
    else:
        favorable = position.entry_price - bar.low
        adverse = bar.high - position.entry_price
    position.mfe = max(position.mfe, max(0.0, favorable))
    position.mae = max(position.mae, max(0.0, adverse))


class ReplaySimulator:
    """Chronological stateful replay: decisions + one simulated position."""

    def __init__(
        self,
        *,
        system_config: SystemConfig,
        execution: ReplayExecutionConfig | None = None,
        account_id: str = 'replay',
        magic: int = 100001,
        relative_spread: float = 1.0,
        news_events: tuple[dict[str, object], ...] | None = None,
        write_signal_audit: bool = False,
    ) -> None:
        self.system_config = system_config
        self.execution = execution or default_replay_execution_config()
        self.account_id = account_id
        self.magic = magic
        self.relative_spread = relative_spread
        self.news_events = news_events
        self.write_signal_audit = write_signal_audit
        self.position_state: PositionState = 'FLAT'
        self.pending: PendingEntry | None = None
        self.open_position: OpenPosition | None = None
        self.closed_trades: list[ClosedTrade] = []
        self.signal_audit: list[dict[str, Any]] = []
        self.decision_counts: Counter[str] = Counter()
        self.reason_counts: Counter[str] = Counter()
        self.buy_scores: list[float] = []
        self.sell_scores: list[float] = []
        self.score_deltas: list[float] = []
        self.market_qualities: list[float] = []
        self.duplicate_rejections = 0
        self.cooldown_rejections = 0
        self._trade_seq = 0
        self.instance_state: InstanceState | None = None
        self.symbol = ''
        self.control_files_written = 0

    def run(self, bars: tuple[NormalizedMarketBar, ...], *, min_bars: int | None = None) -> dict[str, Any]:
        if not bars:
            raise ValueError('bars required')
        lookback = max(3, int(self.system_config.analysis.lookback_bars))
        structure_lookback = max(2, int(self.system_config.analysis.structure_lookback_bars))
        required = max(3, min_bars or 3)
        preferred = max(structure_lookback, lookback)
        start_index = preferred if len(bars) >= preferred else required
        self.symbol = bars[0].symbol
        instance = Instance(account_id=self.account_id, symbol=self.symbol, magic=self.magic)
        self.instance_state = InstanceState(instance=instance)
        self.instance_state.update_instrument(
            digits=bars[0].digits,
            point=bars[0].point,
            pip=bars[0].point * 10.0 if bars[0].digits >= 3 else bars[0].point,
        )
        evaluated = 0
        for end in range(start_index, len(bars) + 1):
            window = tuple(bars[:end])
            bar = window[-1]
            bar_utc = format_utc_timestamp(bar.time_utc)
            # Manage open / pending against this newly closed bar first.
            self._process_bar_for_position(window)
            universe, news_meta = build_replay_universe(
                bars=window,
                timezone_name=self.execution.timezone_name,
                news_events=self.news_events,
            )
            # Only evaluate new entries when flat (and not pending fill).
            allow_decision = self.position_state == 'FLAT' and self.pending is None
            result = run_decision_engine(
                universe=universe,
                market_bars=window,
                instance_state=self.instance_state,
                relative_spread=self.relative_spread,
                system_config=self.system_config,
                execution_possible=allow_decision,
            )
            evaluated += 1
            self.decision_counts[result.decision] += 1
            quality = result.signal_quality
            reason_code = quality.reason_code if quality is not None and quality.reason_code else (
                result.reason.split(':', 1)[0].strip() if ':' in result.reason else (result.reason.strip() or 'NONE')
            )
            self.reason_counts[reason_code] += 1
            if reason_code == 'DUPLICATE_SIGNAL':
                self.duplicate_rejections += 1
            if reason_code == 'TRADE_COOLDOWN_ACTIVE':
                self.cooldown_rejections += 1
            self.buy_scores.append(float(result.buy_score))
            self.sell_scores.append(float(result.sell_score))
            if quality is not None:
                self.score_deltas.append(float(quality.score_delta))
                self.market_qualities.append(float(quality.market_quality_score))
            if self.write_signal_audit:
                self.signal_audit.append(
                    {
                        'bar_utc': bar_utc,
                        'decision': result.decision,
                        'reason_code': reason_code,
                        'buy_score': result.buy_score,
                        'sell_score': result.sell_score,
                        'session': universe.session,
                        'regime': universe.market_regime,
                        'news_meta': news_meta,
                        'fingerprint': quality.fingerprint if quality else None,
                        'position_state': self.position_state,
                    }
                )
            if allow_decision and result.decision in {Decision.BUY.value, Decision.SELL.value} and quality is not None and quality.passed:
                candidate = result.buy_candidate if result.decision == Decision.BUY.value else result.sell_candidate
                self.pending = PendingEntry(
                    side=result.decision,
                    signal_bar_utc=bar_utc,
                    signal_time_utc=bar_utc,
                    entry_price_hint=float(candidate.entry_price),
                    stop_loss=float(candidate.stop_loss),
                    take_profit=float(candidate.take_profit),
                    fingerprint=quality.fingerprint,
                    setup_type=quality.setup_type,
                    buy_score=float(result.buy_score),
                    sell_score=float(result.sell_score),
                    score_delta=float(quality.score_delta),
                    market_quality=float(quality.market_quality_score),
                    confirmation_count=int(quality.confirmation_count),
                    reason=result.reason,
                    session=universe.session,
                    regime=universe.market_regime,
                    signal_snapshot={
                        'reason': result.reason,
                        'confirmations': [item.to_dict() for item in quality.confirmations],
                        'setup_origin_timestamp': quality.setup_origin_timestamp,
                        'structure_id': quality.structure_id,
                        'signal_candle_timestamp': quality.signal_candle_timestamp,
                    },
                )
                self.position_state = 'PENDING_ENTRY'
        # Force-close any leftover open position at last close.
        if self.open_position is not None:
            self._close_position(bars[-1], exit_price=bars[-1].close, exit_reason='END_OF_DATA', point=bars[-1].point)
        return self.build_summary(total_bars=len(bars), evaluated_bars=evaluated)

    def _process_bar_for_position(self, window: tuple[NormalizedMarketBar, ...]) -> None:
        bar = window[-1]
        bar_utc = format_utc_timestamp(bar.time_utc)
        point = bar.point
        assert self.instance_state is not None
        # Fill pending on next bar open.
        if self.pending is not None and self.position_state == 'PENDING_ENTRY':
            if bar_utc > self.pending.signal_bar_utc:
                entry = _apply_entry_costs(
                    side=self.pending.side,
                    raw_open=bar.open,
                    spread=self.execution.spread_price,
                    slippage=self.execution.slippage_price,
                )
                self._trade_seq += 1
                self.open_position = OpenPosition(
                    trade_id=f'T{self._trade_seq:05d}',
                    side=self.pending.side,
                    fingerprint=self.pending.fingerprint,
                    setup_type=self.pending.setup_type,
                    signal_time_utc=self.pending.signal_time_utc,
                    entry_time_utc=bar_utc,
                    entry_price=entry,
                    stop_loss=self.pending.stop_loss,
                    take_profit=self.pending.take_profit,
                    spread=self.execution.spread_price,
                    slippage=self.execution.slippage_price,
                    commission=self.execution.commission_per_trade,
                    buy_score=self.pending.buy_score,
                    sell_score=self.pending.sell_score,
                    score_delta=self.pending.score_delta,
                    market_quality=self.pending.market_quality,
                    confirmation_count=self.pending.confirmation_count,
                    session=self.pending.session,
                    regime=self.pending.regime,
                    signal_snapshot=dict(self.pending.signal_snapshot),
                )
                if self.pending.fingerprint:
                    self.instance_state.register_signal_fingerprint(
                        self.pending.fingerprint,
                        expiry_bars=self.system_config.signal_quality.duplicate_signal_expiry_bars,
                    )
                self.pending = None
                self.position_state = 'OPEN'
        if self.open_position is None:
            return
        position = self.open_position
        if bar_utc <= position.entry_time_utc:
            return
        position.bars_open += 1
        _update_excursion(position=position, bar=bar)
        resolved = _resolve_intrabar_exit(
            side=position.side,
            bar=bar,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            conflict_rule=self.execution.intrabar_conflict_rule,
        )
        if resolved is None:
            return
        exit_reason, exit_price = resolved
        self._close_position(bar, exit_price=exit_price, exit_reason=exit_reason, point=point)

    def _close_position(self, bar: NormalizedMarketBar, *, exit_price: float, exit_reason: str, point: float) -> None:
        assert self.open_position is not None and self.instance_state is not None
        position = self.open_position
        bar_utc = format_utc_timestamp(bar.time_utc)
        gross = _gross_pnl(
            side=position.side,
            entry=position.entry_price,
            exit_price=exit_price,
            lot_size=self.execution.lot_size,
            point_value_per_lot=self.execution.point_value_per_lot,
            point=point,
        )
        net = gross - position.commission
        result_r = _r_multiple(side=position.side, entry=position.entry_price, exit_price=exit_price, stop_loss=position.stop_loss)
        outcome = _outcome_from_r(result_r)
        trade = ClosedTrade(
            trade_id=position.trade_id,
            fingerprint=position.fingerprint,
            symbol=self.symbol,
            timeframe='M1',
            side=position.side,
            setup_type=position.setup_type,
            signal_time=position.signal_time_utc,
            entry_time=position.entry_time_utc,
            entry_price=position.entry_price,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            exit_time=bar_utc,
            exit_price=exit_price,
            exit_reason=exit_reason,
            outcome=outcome,
            spread=position.spread,
            slippage=position.slippage,
            commission=position.commission,
            gross_result=gross,
            net_result=net,
            result_r=result_r,
            mfe=position.mfe,
            mae=position.mae,
            buy_score=position.buy_score,
            sell_score=position.sell_score,
            score_delta=position.score_delta,
            market_quality=position.market_quality,
            confirmation_count=position.confirmation_count,
            session=position.session,
            regime=position.regime,
            duration_bars=position.bars_open,
        )
        self.closed_trades.append(trade)
        self.instance_state.register_trade_close(
            close_bar_utc=bar_utc,
            close_time_utc=bar_utc,
            outcome=outcome,
            cooldown_bars_after_trade=self.system_config.signal_quality.cooldown_bars_after_trade,
            cooldown_bars_after_loss=self.system_config.signal_quality.cooldown_bars_after_loss,
        )
        self.open_position = None
        self.position_state = 'FLAT'

    def build_summary(self, *, total_bars: int, evaluated_bars: int) -> dict[str, Any]:
        closed = self.closed_trades
        wins = sum(1 for t in closed if t.outcome == TradeOutcome.WIN.value)
        losses = sum(1 for t in closed if t.outcome == TradeOutcome.LOSS.value)
        breakeven = sum(1 for t in closed if t.outcome == TradeOutcome.BREAKEVEN.value)
        unknown = sum(1 for t in closed if t.outcome == TradeOutcome.UNKNOWN.value)
        gross_profit = sum(t.gross_result for t in closed if t.gross_result > 0)
        gross_loss = sum(t.gross_result for t in closed if t.gross_result < 0)
        net = sum(t.net_result for t in closed)
        total_r = sum(t.result_r for t in closed)
        avg_r = (total_r / len(closed)) if closed else 0.0
        win_rate = (wins / len(closed)) if closed else 0.0
        expectancy = avg_r
        profit_factor = (gross_profit / abs(gross_loss)) if gross_loss < 0 else (float('inf') if gross_profit > 0 else 0.0)
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        max_dd_r = 0.0
        equity_r = 0.0
        peak_r = 0.0
        consec = 0
        max_consec = 0
        for trade in closed:
            equity += trade.net_result
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)
            equity_r += trade.result_r
            peak_r = max(peak_r, equity_r)
            max_dd_r = max(max_dd_r, peak_r - equity_r)
            if trade.outcome == TradeOutcome.LOSS.value:
                consec += 1
                max_consec = max(max_consec, consec)
            else:
                consec = 0
        avg_duration = (sum(t.duration_bars for t in closed) / len(closed)) if closed else 0.0
        avg_mfe = (sum(t.mfe for t in closed) / len(closed)) if closed else 0.0
        avg_mae = (sum(t.mae for t in closed) / len(closed)) if closed else 0.0
        buy = self.decision_counts.get(Decision.BUY.value, 0)
        sell = self.decision_counts.get(Decision.SELL.value, 0)
        wait = self.decision_counts.get(Decision.WAIT.value, 0)
        block = self.decision_counts.get(Decision.BLOCK.value, 0)
        wait_pct = (100.0 * wait / evaluated_bars) if evaluated_bars else 0.0

        def _avg(values: list[float]) -> float:
            return sum(values) / len(values) if values else 0.0

        by_side: dict[str, Any] = {}
        for side in (Side.BUY.value, Side.SELL.value):
            subset = [t for t in closed if t.side == side]
            by_side[side] = {
                'closed_trades': len(subset),
                'wins': sum(1 for t in subset if t.outcome == TradeOutcome.WIN.value),
                'losses': sum(1 for t in subset if t.outcome == TradeOutcome.LOSS.value),
                'net_result': sum(t.net_result for t in subset),
                'total_r': sum(t.result_r for t in subset),
            }
        by_session: dict[str, int] = Counter(t.session for t in closed)
        by_regime: dict[str, int] = Counter(t.regime for t in closed)
        by_setup: dict[str, int] = Counter(t.setup_type or 'unknown' for t in closed)
        by_exit: dict[str, int] = Counter(t.exit_reason for t in closed)

        return {
            'total_bars': total_bars,
            'evaluated_bars': evaluated_bars,
            'BUY_signal_count': buy,
            'SELL_signal_count': sell,
            'WAIT_count': wait,
            'BLOCK_count': block,
            'WAIT_percentage': wait_pct,
            'reason_codes': dict(self.reason_counts),
            'average_buy_score': _avg(self.buy_scores),
            'average_sell_score': _avg(self.sell_scores),
            'average_score_delta': _avg(self.score_deltas),
            'average_market_quality': _avg(self.market_qualities),
            'opened_trades': self._trade_seq,
            'closed_trades': len(closed),
            'wins': wins,
            'losses': losses,
            'breakeven': breakeven,
            'unknown_outcomes': unknown,
            'win_rate': win_rate,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'net_result': net,
            'total_R': total_r,
            'average_R_per_trade': avg_r,
            'expectancy': expectancy,
            'profit_factor': profit_factor if profit_factor != float('inf') else None,
            'maximum_drawdown': max_dd,
            'maximum_drawdown_R': max_dd_r,
            'maximum_consecutive_losses': max_consec,
            'average_trade_duration': avg_duration,
            'MFE': avg_mfe,
            'MAE': avg_mae,
            'duplicate_signal_rejection_count': self.duplicate_rejections,
            'cooldown_rejection_count': self.cooldown_rejections,
            'by_side': by_side,
            'by_session': dict(by_session),
            'by_regime': dict(by_regime),
            'by_setup_type': dict(by_setup),
            'by_exit_reason': dict(by_exit),
            'control_files_written': self.control_files_written,
            'execution_model': asdict(self.execution),
            # Compat with replay v1 summary keys
            'bars_total': total_bars,
            'windows_evaluated': evaluated_bars,
            'decisions': dict(self.decision_counts),
            'buy': buy,
            'sell': sell,
            'wait': wait,
            'block': block,
        }

    def write_outputs(self, *, output_dir: Path, summary: dict[str, Any]) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_path = output_dir / 'replay_summary.json'
        ledger_path = output_dir / 'replay_trades.jsonl'
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        with ledger_path.open('w', encoding='utf-8') as handle:
            for trade in self.closed_trades:
                handle.write(json.dumps(asdict(trade), sort_keys=True) + '\n')
        csv_path = output_dir / 'replay_trades.csv'
        fieldnames = list(asdict(self.closed_trades[0]).keys()) if self.closed_trades else [
            'trade_id', 'fingerprint', 'symbol', 'timeframe', 'side', 'setup_type', 'signal_time',
            'entry_time', 'entry_price', 'stop_loss', 'take_profit', 'exit_time', 'exit_price',
            'exit_reason', 'outcome', 'spread', 'slippage', 'commission', 'gross_result', 'net_result',
            'result_r', 'mfe', 'mae', 'buy_score', 'sell_score', 'score_delta', 'market_quality',
            'confirmation_count', 'session', 'regime', 'duration_bars',
        ]
        with csv_path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for trade in self.closed_trades:
                writer.writerow(asdict(trade))
        paths = {'summary': summary_path, 'ledger_jsonl': ledger_path, 'ledger_csv': csv_path}
        if self.write_signal_audit:
            audit_path = output_dir / 'replay_signal_audit.jsonl'
            with audit_path.open('w', encoding='utf-8') as handle:
                for row in self.signal_audit:
                    handle.write(json.dumps(row, sort_keys=True) + '\n')
            paths['signal_audit'] = audit_path
        return paths


def run_replay(
    *,
    market_path: Path,
    config_path: Path | None = None,
    account_id: str = 'replay',
    magic: int = 100001,
    relative_spread: float = 1.0,
    min_bars: int | None = None,
    execution: ReplayExecutionConfig | None = None,
    news_events: tuple[dict[str, object], ...] | None = None,
    write_signal_audit: bool = False,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    system_config = load_system_config(config_path or root / 'config' / 'system.json', system_paths=SystemPaths(root))
    bars = normalize_market_csv(market_path.read_text(encoding='utf-8'))
    simulator = ReplaySimulator(
        system_config=system_config,
        execution=execution,
        account_id=account_id,
        magic=magic,
        relative_spread=relative_spread,
        news_events=news_events,
        write_signal_audit=write_signal_audit,
    )
    summary = simulator.run(bars, min_bars=min_bars)
    summary['market_path'] = str(market_path)
    if output_dir is not None:
        paths = simulator.write_outputs(output_dir=output_dir, summary=summary)
        summary['output_paths'] = {key: str(value) for key, value in paths.items()}
    summary['_simulator'] = simulator
    return summary
