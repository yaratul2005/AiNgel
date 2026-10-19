import json
from pathlib import Path

from aingel.body.registry import ToolRegistry
from aingel.body.tools.base import Risk, ToolSpec
from aingel.brain.base import Response, ToolCall
from aingel.brain.fake import ScriptedBrain
from aingel.conscience.audit import AuditLog
from aingel.conscience.budgets import Budget
from aingel.conscience.killswitch import KillSwitch
from aingel.conscience.permissions import Conscience, Verdict
from aingel.heartbeat import run_tick


class FakeTool:
    def __init__(self, spec: ToolSpec, audit: AuditLog | None = None) -> None:
        self.spec = spec
        self.audit = audit
        self.calls: list[dict[str, object]] = []

    def run(self, **args: object) -> str:
        if self.audit is not None:
            assert self.audit.events[-1].outcome == "authorized"
        self.calls.append(args)
        return "ok"


def test_conscience_allows_only_low_risk_sandbox_safe_tools() -> None:
    conscience = Conscience("sandbox")
    safe = FakeTool(ToolSpec("safe", "safe", Risk.LOW, sandbox_safe=True))
    unsafe = FakeTool(ToolSpec("unsafe", "unsafe", Risk.LOW))
    dangerous = FakeTool(ToolSpec("dangerous", "dangerous", Risk.HIGH, sandbox_safe=True))

    assert conscience.check(safe, {}).verdict is Verdict.ALLOW
    assert conscience.check(unsafe, {}).verdict is Verdict.DENY
    assert conscience.check(dangerous, {}).verdict is Verdict.DENY
    assert conscience.check(None, {}).verdict is Verdict.DENY


def test_invalid_arguments_are_denied_before_tool_execution() -> None:
    tool = FakeTool(
        ToolSpec(
            "note",
            "record note",
            Risk.LOW,
            sandbox_safe=True,
            schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        )
    )
    audit = AuditLog()
    result = run_tick(
        ScriptedBrain([Response(tool_calls=[ToolCall("note", {"text": 3})])]),
        ToolRegistry([tool]),
        Conscience("sandbox"),
        Budget(1),
        audit,
    )

    assert not tool.calls
    assert result.actions[0].verdict is Verdict.DENY
    assert audit.events[0].outcome == "not_executed"


def test_approved_decision_is_audited_before_execution() -> None:
    audit = AuditLog()
    tool = FakeTool(ToolSpec("safe", "safe", Risk.LOW, sandbox_safe=True), audit)
    result = run_tick(
        ScriptedBrain([Response(tool_calls=[ToolCall("safe")])]),
        ToolRegistry([tool]),
        Conscience("sandbox"),
        Budget(1),
        audit,
    )

    assert result.actions[0].outcome == "executed"
    assert [event.outcome for event in audit.events] == ["authorized", "executed"]


def test_jsonl_audit_persists_events_without_call_arguments(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    audit = AuditLog(audit_path)
    tool = FakeTool(ToolSpec("safe", "safe", Risk.LOW, sandbox_safe=True))
    run_tick(
        ScriptedBrain([Response(tool_calls=[ToolCall("safe", {"private_value": "omit-me"})])]),
        ToolRegistry([tool]),
        Conscience("sandbox"),
        Budget(1),
        audit,
    )

    entries = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert [entry["outcome"] for entry in entries] == ["authorized", "executed"]
    assert "omit-me" not in audit_path.read_text(encoding="utf-8")


def test_supervised_risky_action_asks_and_is_not_run() -> None:
    high = FakeTool(ToolSpec("high", "high risk", Risk.HIGH))
    result = run_tick(
        ScriptedBrain([Response(tool_calls=[ToolCall("high")])]),
        ToolRegistry([high]),
        Conscience("supervised"),
        Budget(1),
        AuditLog(),
    )

    assert result.actions[0].verdict is Verdict.ASK_HUMAN
    assert result.actions[0].outcome == "not_executed"
    assert not high.calls


def test_budget_counts_denied_proposals_and_kill_switch_stops_calls(tmp_path: Path) -> None:
    safe = FakeTool(ToolSpec("safe", "safe", Risk.LOW, sandbox_safe=True))
    high = FakeTool(ToolSpec("high", "high", Risk.HIGH))
    audit = AuditLog()
    result = run_tick(
        ScriptedBrain(
            [
                Response(
                    tool_calls=[
                        ToolCall("safe"),
                        ToolCall("high"),
                        ToolCall("safe"),
                    ]
                )
            ]
        ),
        ToolRegistry([safe, high]),
        Conscience("sandbox"),
        Budget(2),
        audit,
    )

    assert len(result.actions) == 3
    assert result.actions[1].verdict is Verdict.DENY
    assert result.actions[2].reason == "step budget exhausted"
    assert len(safe.calls) == 1

    kill_flag = tmp_path / "STOP"
    switch = KillSwitch(kill_flag)
    kill_flag.touch()
    stopped = run_tick(
        ScriptedBrain([Response(tool_calls=[ToolCall("safe")])]),
        ToolRegistry([safe]),
        Conscience("sandbox", switch),
        Budget(2),
        AuditLog(),
    )
    assert stopped.stopped_reason == "kill switch is engaged"
    assert len(safe.calls) == 1


def test_kill_switch_engaged_by_tool_audits_and_stops_following_call() -> None:
    switch = KillSwitch()

    class StoppingTool(FakeTool):
        def run(self, **args: object) -> str:
            self.calls.append(args)
            switch.engage()
            return "stopped"

    stopping_tool = StoppingTool(
        ToolSpec("stop", "engages the stop", Risk.LOW, sandbox_safe=True)
    )
    safe = FakeTool(ToolSpec("safe", "safe", Risk.LOW, sandbox_safe=True))
    audit = AuditLog()
    result = run_tick(
        ScriptedBrain(
            [Response(tool_calls=[ToolCall("stop"), ToolCall("safe")])]
        ),
        ToolRegistry([stopping_tool, safe]),
        Conscience("sandbox", switch),
        Budget(2),
        audit,
    )

    assert len(stopping_tool.calls) == 1
    assert not safe.calls
    assert result.stopped_reason == "kill switch is engaged"
    assert audit.events[-1].tool_name == "safe"
    assert audit.events[-1].verdict == Verdict.DENY.value
