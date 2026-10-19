"""Single-tick runner that routes every proposed action through conscience."""

from __future__ import annotations

from dataclasses import dataclass, field

from .brain.base import Brain, Response, ToolCall
from .body.registry import ToolRegistry
from .conscience.audit import AuditLog
from .conscience.budgets import Budget
from .conscience.permissions import Conscience, Verdict


@dataclass(frozen=True)
class ActionResult:
    """Observable, non-sensitive summary of an attempted action."""

    tool_name: str
    verdict: Verdict
    reason: str
    outcome: str


@dataclass
class TickResult:
    """Results from one brain response and its proposed actions."""

    response_text: str = ""
    actions: list[ActionResult] = field(default_factory=list)
    stopped_reason: str | None = None


def run_tick(
    brain: Brain,
    tools: ToolRegistry,
    conscience: Conscience,
    budget: Budget,
    audit: AuditLog,
    *,
    system: str = "You are an agent operating under explicit safety policy.",
    context: str = "",
) -> TickResult:
    """Run one decision tick; malformed calls and execution failures fail closed."""
    if conscience.killswitch.engaged:
        return TickResult(stopped_reason="kill switch is engaged")
    if budget.exhausted:
        return TickResult(stopped_reason="step budget exhausted")

    response = brain.think(system, context, tools.specs())
    if not isinstance(response, Response):
        raise TypeError("Brain.think() must return a Response")
    result = TickResult(response_text=response.text)

    for call in response.tool_calls:
        if (
            not isinstance(call, ToolCall)
            or not isinstance(call.name, str)
            or not isinstance(call.args, dict)
        ):
            raise TypeError("Brain returned a malformed tool call")
        if conscience.killswitch.engaged:
            decision = conscience.check(None)
            audit.record(call.name, decision.verdict.value, decision.reason, "not_executed")
            result.actions.append(
                ActionResult(call.name, decision.verdict, decision.reason, "not_executed")
            )
            result.stopped_reason = decision.reason
            break

        if not budget.consume():
            reason = "step budget exhausted"
            audit.record(call.name, Verdict.DENY.value, reason, "not_executed")
            result.actions.append(ActionResult(call.name, Verdict.DENY, reason, "not_executed"))
            result.stopped_reason = reason
            break

        tool = tools.get(call.name)
        decision = conscience.check(tool, call.args)
        outcome = "not_executed"
        authorized = decision.verdict is Verdict.ALLOW
        audit.record(
            call.name,
            decision.verdict.value,
            decision.reason,
            "authorized" if authorized else "not_executed",
        )
        if authorized and tool is not None:
            try:
                tool.run(**call.args)
                outcome = "executed"
            except Exception as error:
                decision = type(decision)(
                    decision.verdict,
                    f"tool execution failed: {type(error).__name__}",
                )
                outcome = "failed"

        if authorized:
            audit.record(call.name, decision.verdict.value, decision.reason, outcome)
        result.actions.append(ActionResult(call.name, decision.verdict, decision.reason, outcome))
        if conscience.killswitch.engaged:
            result.stopped_reason = "kill switch is engaged"
            break
        if budget.exhausted and len(response.tool_calls) > len(result.actions):
            result.stopped_reason = "step budget exhausted"

    return result
