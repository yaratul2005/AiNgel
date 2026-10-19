from pathlib import Path

from aingel.body.registry import ToolRegistry
from aingel.body.tools.base import Risk, ToolSpec
from aingel.brain.base import Response, ToolCall
from aingel.brain.fake import ScriptedBrain
from aingel.conscience.audit import AuditLog
from aingel.conscience.budgets import Budget
from aingel.conscience.permissions import Conscience
from aingel.heartbeat import run_soul_tick
from aingel.soul.affect import Affect
from aingel.soul.identity import Identity
from aingel.soul.memory.store import MemoryStore
from aingel.soul.state import Soul


class MemoryTool:
    spec = ToolSpec("record", "record in memory", Risk.LOW, sandbox_safe=True)

    def run(self, **args: object) -> str:
        del args
        return "ok"


class ContextBrain:
    def __init__(self) -> None:
        self.contexts: list[str] = []
        self._script = ScriptedBrain(
            [
                Response(tool_calls=[ToolCall("record")]),
                Response(tool_calls=[ToolCall("record")]),
            ]
        )

    def think(self, system: str, context: str, tools: list[dict[str, object]]) -> Response:
        self.contexts.append(context)
        return self._script.think(system, context, tools)


def test_soul_context_and_memory_persist_across_ticks_and_restart(tmp_path: Path) -> None:
    database = tmp_path / "memory.sqlite3"
    soul = Soul(Identity("Aingel"), Affect(), MemoryStore(database))
    brain = ContextBrain()
    tools = ToolRegistry([MemoryTool()])
    conscience = Conscience("sandbox")
    budget = Budget(3)

    first = run_soul_tick(brain, tools, conscience, budget, AuditLog(), soul)
    second = run_soul_tick(brain, tools, conscience, budget, AuditLog(), soul)
    assert first.actions[0].outcome == "executed"
    assert second.actions[0].outcome == "executed"
    assert "Action record verdict=allow outcome=executed" in brain.contexts[1]
    soul.memory.close()

    reopened = MemoryStore(database)
    try:
        assert len(reopened.recall("Action record", k=10)) == 2
    finally:
        reopened.close()
