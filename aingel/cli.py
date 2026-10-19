"""Command line entry points for Aingel."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .body.registry import ToolRegistry
from .body.tools.base import Risk, ToolSpec
from .brain.base import Response, ToolCall
from .brain.fake import ScriptedBrain
from .brain.ollama import OllamaBrain, OllamaError
from .config import AgentConfig, load_config
from .conscience.audit import AuditLog
from .conscience.budgets import Budget
from .conscience.permissions import Conscience
from .heartbeat import run_soul_tick
from .soul.affect import Affect
from .soul.agenda import Agenda
from .soul.identity import Identity
from .soul.memory.store import MemoryStore
from .soul.state import Soul


@dataclass
class _DemoTool:
    """Harmless in-memory demonstration capability."""

    spec: ToolSpec
    calls: int = 0

    def run(self, **args: object) -> str:
        """Count execution without touching external state."""
        del args
        self.calls += 1
        return "demo action completed"


def _demo(config: AgentConfig, read_file: str | None = None) -> int:
    """Run two fully offline ticks with persistent in-session memory."""
    safe_tool = _DemoTool(
        ToolSpec(
            "record_note",
            "Record an in-memory demo note",
            Risk.LOW,
            True,
            {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        )
    )
    dangerous_tool = _DemoTool(
        ToolSpec("delete_file", "Demonstration high-risk operation", Risk.HIGH)
    )
    first_calls = (
        [ToolCall("workspace_read", {"path": read_file})]
        if read_file is not None
        else [ToolCall("record_note", {"text": "hello"})]
    )
    brain = ScriptedBrain(
        [
            Response(
                text="First tick: perform the configured read or record a note.",
                tool_calls=first_calls,
            ),
            Response(
                text="Second tick: consider a high-risk request and another note.",
                tool_calls=[
                    ToolCall("delete_file", {"path": "example.txt"}),
                    ToolCall("record_note", {"text": "budget boundary"}),
                ],
            ),
        ]
    )
    audit = AuditLog()
    memory = MemoryStore(":memory:")
    agenda = Agenda(memory)
    demo_goal = agenda.add_goal("Complete the offline safety demonstration", priority=1.0)
    agenda.activate_next_goal()
    agenda.commit_plan(
        demo_goal.goal_id,
        ("perform the first tick", "review action outcomes and safety gates"),
    )
    soul = Soul(Identity("Aingel"), Affect(), memory, agenda)
    tools = ToolRegistry.from_config(config, [safe_tool, dangerous_tool])
    conscience = Conscience(config.conscience.mode)
    budget = Budget(config.heartbeat.max_steps_per_session)
    first_tick = run_soul_tick(brain, tools, conscience, budget, audit, soul)
    second_tick = run_soul_tick(
        brain,
        tools,
        conscience,
        budget,
        audit,
        soul,
        previous_result=first_tick,
    )
    ticks = [first_tick, second_tick]
    output = {
        "ticks": [asdict(tick) for tick in ticks],
        "second_tick_context": brain.contexts[1],
        "memory": memory.summarize_recent(),
        "executions": {"record_note": safe_tool.calls, "delete_file": dangerous_tool.calls},
        "audit": [asdict(event) for event in audit.events],
    }
    print(json.dumps(output, default=str, indent=2))
    memory.close()
    return 0


def _run_prompt(config: AgentConfig, prompt: str) -> int:
    """Run one explicitly requested Ollama tick through the normal safety gates."""
    if config.brain.provider != "ollama" or config.brain.model is None:
        raise ValueError(
            "--prompt requires [brain] provider = 'ollama' and a configured brain.model"
        )
    if not prompt.strip():
        raise ValueError("--prompt must contain non-whitespace text")

    brain = OllamaBrain(
        config.brain.model,
        config.brain.base_url,
        timeout=config.brain.timeout,
    )
    memory = MemoryStore(":memory:")
    try:
        soul = Soul(Identity("Aingel"), Affect(), memory)
        tools = ToolRegistry.from_config(config)
        audit = AuditLog()
        budget = Budget(config.heartbeat.max_steps_per_session)
        result = run_soul_tick(
            brain,
            tools,
            Conscience(config.conscience.mode),
            budget,
            audit,
            soul,
            memory_query=prompt,
            user_input=prompt,
        )
        output = {
            "tick": asdict(result),
            "budget": {
                "max_steps": budget.max_steps,
                "steps_used": budget.steps_used,
            },
            "audit": [asdict(event) for event in audit.events],
        }
        print(json.dumps(output, default=str, indent=2))
        return 0
    finally:
        memory.close()


def main(argv: list[str] | None = None) -> int:
    """Run the offline demo or one explicitly configured Ollama prompt."""
    parser = argparse.ArgumentParser(prog="aingel", description="Aingel agent framework")
    parser.add_argument("--config", type=Path, help="Optional TOML configuration file")
    parser.add_argument("--mode", choices=["sandbox", "supervised", "autonomous"])
    parser.add_argument("--max-steps", type=int, help="Override the per-session action budget")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument(
        "--demo", action="store_true", help="Run the offline multi-tick demonstration"
    )
    operation.add_argument(
        "--prompt", help="Run one Ollama-backed tick (requires explicit [brain] configuration)"
    )
    parser.add_argument(
        "--read-file",
        help="Read this relative file from [body].workspace_root (requires supervised mode)",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config) if args.config else AgentConfig()
        if args.max_steps is not None:
            if args.max_steps < 1:
                raise ValueError("--max-steps must be a positive integer")
            config = replace(
                config,
                heartbeat=replace(config.heartbeat, max_steps_per_session=args.max_steps),
            )
        if args.mode is not None:
            config = replace(config, conscience=replace(config.conscience, mode=args.mode))
        if args.read_file is not None:
            if not args.demo:
                raise ValueError("--read-file is only available in the offline --demo")
            if config.body.workspace_root is None:
                raise ValueError("--read-file requires [body].workspace_root in the config")
            if config.conscience.mode != "supervised":
                raise ValueError("--read-file requires conscience.mode = 'supervised'")
        if args.demo:
            return _demo(config, args.read_file)
        if args.prompt is not None:
            return _run_prompt(config, args.prompt)
        parser.error("choose --demo (offline) or --prompt (configured Ollama)")
    except ValueError as error:
        print(f"aingel: {error}", file=sys.stderr)
        return 2
    except OllamaError as error:
        print(f"aingel: {error}", file=sys.stderr)
        return 1
