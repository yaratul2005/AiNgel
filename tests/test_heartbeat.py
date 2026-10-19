from aingel.body.registry import ToolRegistry
from aingel.body.tools.base import Risk, ToolSpec
from aingel.brain.base import Response, ToolCall
from aingel.brain.fake import ScriptedBrain
from aingel.conscience.audit import AuditLog
from aingel.conscience.budgets import Budget
from aingel.conscience.permissions import Conscience
from aingel.heartbeat import run_tick
from aingel.proposals import AgendaProposal, GoalProposal


class RecordingTool:
    spec = ToolSpec("record", "record an in-memory value", Risk.LOW, sandbox_safe=True)

    def __init__(self) -> None:
        self.calls = 0

    def run(self, **args: object) -> str:
        self.calls += 1
        return "recorded"


def test_tick_calls_brain_then_routes_each_proposal_through_audit() -> None:
    tool = RecordingTool()
    audit = AuditLog()
    result = run_tick(
        ScriptedBrain([Response("done", [ToolCall("record")])]),
        ToolRegistry([tool]),
        Conscience("sandbox"),
        Budget(2),
        audit,
    )

    assert result.response_text == "done"
    assert tool.calls == 1
    assert [event.outcome for event in audit.events] == ["authorized", "executed"]


def test_tick_surfaces_state_proposal_without_applying_it() -> None:
    proposal = AgendaProposal(goals=(GoalProposal("inspect report"),))
    result = run_tick(
        ScriptedBrain([Response("candidate", agenda_proposal=proposal)]),
        ToolRegistry([]),
        Conscience("sandbox"),
        Budget(2),
        AuditLog(),
    )

    assert result.agenda_proposal is proposal
