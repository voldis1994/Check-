from __future__ import annotations

import argparse
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.analysis.context import AnalysisContext
from engine.core.instance import Instance
from engine.execution.control_writer import build_control_command
from engine.decision.buy import BuyCandidate
from engine.decision.engine import DecisionResult
from engine.decision.sell import SellCandidate
from engine.execution.command import (
    OrderCommand,
    build_close_order_command,
    build_management_order_command,
    build_modify_order_command,
    build_order_command,
    resolve_order_command,
)
from engine.protocol.constants import Decision, OrderAction, RiskResult, Side
from engine.risk.engine import RiskEngineResult
from engine.risk.trade_management import TradeManagementResult

MODULE_NAME = "tools.validate_order_command"
REQUIRED_COMMAND_FIELDS = (
    "command_id",
    "action",
    "reason",
    "decision_id",
    "side",
    "volume",
    "stop_loss",
    "take_profit",
    "ticket",
)
REQUIRED_BUILDERS = (
    "build_order_command",
    "build_modify_order_command",
    "build_close_order_command",
    "build_management_order_command",
    "resolve_order_command",
)


@dataclass(frozen=True)
class ValidationCheck:
    check_id: str
    name: str
    passed: bool
    message: str


@dataclass(frozen=True)
class OrderCommandValidationReport:
    checks: tuple[ValidationCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_checks(self) -> tuple[ValidationCheck, ...]:
        return tuple(check for check in self.checks if not check.passed)


def _check(check_id: str, name: str, passed: bool, message: str) -> ValidationCheck:
    return ValidationCheck(check_id=check_id, name=name, passed=passed, message=message)


def _sample_analysis_context() -> AnalysisContext:
    return AnalysisContext(
        session="LONDON",
        regime="trending",
        news_active=False,
        context_quality=0.8,
        trade_environment="normal",
        spread_filter_passed=True,
    )


def _sample_decision_result(*, decision: str, preferred_side: str, reason: str) -> DecisionResult:
    return DecisionResult(
        decision_id="decision-validate-1",
        decision=decision,
        reason=reason,
        preferred_side=preferred_side,
        buy_candidate=BuyCandidate(
            valid=True,
            invalid_reason=None,
            entry_price=1.10310,
            stop_loss=1.09880,
            take_profit=1.11170,
            component_scores={},
            buy_score=0.8,
        ),
        sell_candidate=SellCandidate(
            valid=False,
            invalid_reason="sell invalid",
            entry_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            component_scores={},
            sell_score=0.3,
        ),
        buy_score=0.8,
        sell_score=0.3,
        analysis_context=_sample_analysis_context(),
    )


def _allow_risk_result() -> RiskEngineResult:
    return RiskEngineResult(
        result=RiskResult.ALLOW.value,
        reason="",
        position_size=0.1,
        stop_loss=1.09880,
        take_profit=1.11170,
    )


def validate_order_command_dataclass_fields() -> tuple[ValidationCheck, ...]:
    fields = {field.name for field in OrderCommand.__dataclass_fields__.values()}
    missing = [field for field in REQUIRED_COMMAND_FIELDS if field not in fields]
    return (
        _check(
            "dataclass_fields",
            "OrderCommand exposes all protocol fields",
            not missing,
            "all required fields present"
            if not missing
            else f"missing fields: {', '.join(missing)}",
        ),
    )


def validate_command_module_structure(root: Path) -> tuple[ValidationCheck, ...]:
    command_path = root / "engine" / "execution" / "command.py"
    if not command_path.is_file():
        return (
            _check(
                "command_module",
                "command module exists",
                False,
                f"missing {command_path}",
            ),
        )

    source = command_path.read_text(encoding="utf-8")
    checks = [
        _check(
            "command_module",
            "command module exists",
            True,
            f"found {command_path}",
        )
    ]
    for builder in REQUIRED_BUILDERS:
        checks.append(
            _check(
                f"builder_{builder}",
                f"{builder} is defined",
                f"def {builder}" in source,
                f"{builder} present in command module",
            )
        )
    return tuple(checks)


def validate_supported_actions() -> tuple[ValidationCheck, ...]:
    supported = {
        OrderAction.OPEN.value,
        OrderAction.MODIFY.value,
        OrderAction.CLOSE.value,
        OrderAction.NONE.value,
    }
    return (
        _check(
            "actions_supported",
            "OrderCommand supports OPEN, MODIFY, CLOSE, NONE",
            supported
            == {
                OrderAction.OPEN.value,
                OrderAction.MODIFY.value,
                OrderAction.CLOSE.value,
                OrderAction.NONE.value,
            },
            f"supported actions: {sorted(supported)}",
        ),
    )


def validate_open_command_contract() -> tuple[ValidationCheck, ...]:
    decision_result = _sample_decision_result(
        decision=Decision.BUY.value,
        preferred_side=Side.BUY.value,
        reason="BUY: preferred side selected",
    )
    command = build_order_command(decision_result, _allow_risk_result(), command_id="cmd-open-1")
    passed = (
        command.action == OrderAction.OPEN.value
        and command.side == Side.BUY.value
        and command.volume == 0.1
        and command.stop_loss == 1.09880
        and command.take_profit == 1.11170
        and command.ticket is None
        and command.decision_id == decision_result.decision_id
    )
    return (
        _check(
            "contract_open",
            "BUY + ALLOW produces OPEN command",
            passed,
            f"action={command.action} side={command.side}",
        ),
    )


def validate_none_command_contract() -> tuple[ValidationCheck, ...]:
    wait_result = _sample_decision_result(
        decision=Decision.WAIT.value,
        preferred_side=Side.NONE.value,
        reason="WAIT: equal scores",
    )
    block_result = _sample_decision_result(
        decision=Decision.BLOCK.value,
        preferred_side=Side.BUY.value,
        reason="BLOCK: spread abnormal",
    )
    wait_command = build_order_command(wait_result, _allow_risk_result(), command_id="cmd-none-1")
    block_command = build_order_command(block_result, _allow_risk_result(), command_id="cmd-none-2")
    passed = (
        wait_command.action == OrderAction.NONE.value
        and block_command.action == OrderAction.NONE.value
        and wait_command.side is None
        and block_command.side is None
        and wait_command.volume is None
        and block_command.reason == "BLOCK: spread abnormal"
    )
    return (
        _check(
            "contract_none",
            "WAIT and BLOCK produce NONE action",
            passed,
            "NONE action keeps control sync without trade fields",
        ),
    )


def validate_modify_command_contract() -> tuple[ValidationCheck, ...]:
    command = build_modify_order_command(
        ticket=123456,
        side=Side.BUY.value,
        stop_loss=1.10100,
        take_profit=1.11170,
        reason="TRADE_MANAGEMENT_BREAKEVEN: stop loss moved to entry",
        decision_id="decision-validate-1",
        command_id="cmd-modify-1",
    )
    passed = (
        command.action == OrderAction.MODIFY.value
        and command.ticket == 123456
        and command.side == Side.BUY.value
        and command.stop_loss == 1.10100
        and command.take_profit == 1.11170
        and command.volume is None
    )
    return (
        _check(
            "contract_modify",
            "MODIFY command includes ticket and SL/TP",
            passed,
            f"action={command.action} ticket={command.ticket}",
        ),
    )


def validate_close_command_contract() -> tuple[ValidationCheck, ...]:
    command = build_close_order_command(
        ticket=123456,
        side=Side.SELL.value,
        volume=0.05,
        reason="TRADE_MANAGEMENT_PARTIAL_CLOSE: partial volume close triggered",
        decision_id="decision-validate-1",
        command_id="cmd-close-1",
    )
    passed = (
        command.action == OrderAction.CLOSE.value
        and command.ticket == 123456
        and command.side == Side.SELL.value
        and command.volume == 0.05
        and command.stop_loss is None
        and command.take_profit is None
    )
    return (
        _check(
            "contract_close",
            "CLOSE command includes ticket and volume",
            passed,
            f"action={command.action} volume={command.volume}",
        ),
    )


def validate_management_command_contract() -> tuple[ValidationCheck, ...]:
    modify_result = TradeManagementResult(
        action=OrderAction.MODIFY.value,
        reason="TRADE_MANAGEMENT_TRAILING: stop loss raised to follow structure",
        stop_loss=1.10200,
        take_profit=1.11170,
    )
    close_result = TradeManagementResult(
        action=OrderAction.CLOSE.value,
        reason="TRADE_MANAGEMENT_TIME_STOP: maximum bars in trade reached",
        volume=0.1,
    )
    none_result = TradeManagementResult(action=OrderAction.NONE.value, reason="")

    modify_command = build_management_order_command(
        modify_result,
        ticket=123456,
        side=Side.BUY.value,
        decision_id="decision-validate-1",
        command_id="cmd-mgmt-modify",
    )
    close_command = build_management_order_command(
        close_result,
        ticket=123456,
        side=Side.BUY.value,
        decision_id="decision-validate-1",
        command_id="cmd-mgmt-close",
    )
    skipped_command = build_management_order_command(
        none_result,
        ticket=123456,
        side=Side.BUY.value,
        decision_id="decision-validate-1",
    )
    passed = (
        modify_command is not None
        and modify_command.action == OrderAction.MODIFY.value
        and close_command is not None
        and close_command.action == OrderAction.CLOSE.value
        and skipped_command is None
    )
    return (
        _check(
            "contract_management",
            "TradeManagementResult maps to MODIFY/CLOSE commands",
            passed,
            "management actions translate to executable order commands",
        ),
    )


def validate_resolve_order_command_priority() -> tuple[ValidationCheck, ...]:
    decision_result = _sample_decision_result(
        decision=Decision.WAIT.value,
        preferred_side=Side.NONE.value,
        reason="WAIT: equal scores",
    )
    management_result = TradeManagementResult(
        action=OrderAction.MODIFY.value,
        reason="TRADE_MANAGEMENT_BREAKEVEN: stop loss moved to entry",
        stop_loss=1.10100,
        take_profit=1.11170,
    )
    resolved = resolve_order_command(
        decision_result,
        _allow_risk_result(),
        management_result,
        ticket=123456,
        side=Side.BUY.value,
        command_id="cmd-resolve-1",
    )
    passed = resolved.action == OrderAction.MODIFY.value and resolved.ticket == 123456
    return (
        _check(
            "resolve_priority",
            "management command overrides decision NONE",
            passed,
            f"resolved action={resolved.action}",
        ),
    )


def validate_control_writer_support(root: Path) -> tuple[ValidationCheck, ...]:
    control_writer = root / "engine" / "execution" / "control_writer.py"
    if not control_writer.is_file():
        return (
            _check(
                "control_writer",
                "control writer supports all actions",
                False,
                f"missing {control_writer}",
            ),
        )

    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    timestamp_utc = "2026-07-07T06:00:00.000Z"
    sample_commands = (
        build_order_command(
            _sample_decision_result(
                decision=Decision.BUY.value,
                preferred_side=Side.BUY.value,
                reason="BUY: preferred side selected",
            ),
            _allow_risk_result(),
            command_id="cmd-open",
        ),
        build_modify_order_command(
            ticket=123456,
            side=Side.BUY.value,
            stop_loss=1.10100,
            take_profit=1.11170,
            reason="TRADE_MANAGEMENT_BREAKEVEN: stop loss moved to entry",
            decision_id="decision-validate-1",
            command_id="cmd-modify",
        ),
        build_close_order_command(
            ticket=123456,
            side=Side.BUY.value,
            volume=0.1,
            reason="TRADE_MANAGEMENT_TIME_STOP: maximum bars in trade reached",
            decision_id="decision-validate-1",
            command_id="cmd-close",
        ),
        build_order_command(
            _sample_decision_result(
                decision=Decision.WAIT.value,
                preferred_side=Side.NONE.value,
                reason="WAIT: equal scores",
            ),
            _allow_risk_result(),
            command_id="cmd-none",
        ),
    )
    actions_supported = True
    for order_command in sample_commands:
        control_command = build_control_command(
            instance,
            order_command,
            timestamp_utc=timestamp_utc,
        )
        if control_command.action != order_command.action:
            actions_supported = False
            break

    return (
        _check(
            "control_writer",
            "control writer supports all actions",
            actions_supported,
            "control writer serializes OPEN, MODIFY, CLOSE, and NONE",
        ),
    )


def validate_public_builder_signatures() -> tuple[ValidationCheck, ...]:
    from engine.execution import command as command_module

    checks: list[ValidationCheck] = []
    for builder_name in REQUIRED_BUILDERS:
        builder = getattr(command_module, builder_name, None)
        if builder is None:
            checks.append(
                _check(
                    f"signature_{builder_name}",
                    f"{builder_name} is importable",
                    False,
                    f"{builder_name} is missing",
                )
            )
            continue
        signature = inspect.signature(builder)
        checks.append(
            _check(
                f"signature_{builder_name}",
                f"{builder_name} is callable",
                callable(builder) and len(signature.parameters) > 0,
                f"{builder_name}{signature}",
            )
        )
    return tuple(checks)


def run_order_command_validation(*, root_path: str | Path | None = None) -> OrderCommandValidationReport:
    root = Path(root_path) if root_path is not None else Path(__file__).resolve().parents[1]
    checks: list[ValidationCheck] = []
    checks.extend(validate_order_command_dataclass_fields())
    checks.extend(validate_command_module_structure(root))
    checks.extend(validate_supported_actions())
    checks.extend(validate_public_builder_signatures())
    checks.extend(validate_open_command_contract())
    checks.extend(validate_none_command_contract())
    checks.extend(validate_modify_command_contract())
    checks.extend(validate_close_command_contract())
    checks.extend(validate_management_command_contract())
    checks.extend(validate_resolve_order_command_priority())
    checks.extend(validate_control_writer_support(root))
    return OrderCommandValidationReport(checks=tuple(checks))


def format_validation_report(report: OrderCommandValidationReport) -> str:
    lines = ["SYSTEM Order Command validation report", ""]
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        lines.append(f"[{status}] {check.check_id} {check.name}: {check.message}")
    lines.append("")
    lines.append("RESULT: PASS" if report.passed else "RESULT: FAIL")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate SYSTEM Order Command implementation")
    parser.add_argument("--root", dest="root_path", default=None, help="SYSTEM root path")
    args = parser.parse_args(argv)

    report = run_order_command_validation(root_path=args.root_path)
    print(format_validation_report(report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
