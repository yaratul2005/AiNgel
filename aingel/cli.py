"""Command line entry points for Aingel."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .brain.base import Response, ToolCall
from .brain.fake import ScriptedBrain
from .body.registry import ToolRegistry
from .body.tools.base import Risk, ToolSpec
from .config import AgentConfig, load_config
from .conscience.audit import AuditLog
from .conscience.budgets import Budget
from .conscience.permissions import Conscience
from .heartbeat import run_tick


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


def _demo(config: AgentConfig) -> int:
    """Run a fully offline example with an allowed and a denied proposal."""
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
    brain = ScriptedBrain(
        [
            Response(
                text="I will record a note, then propose a high-risk operation.",
                tool_calls=[
                    ToolCall("record_note", {"text": "hello"}),
                    ToolCall("delete_file", {"path": "example.txt"}),
                    ToolCall("record_note", {"text": "budget boundary"}),
                ],
            )
        ]
    )
    audit = AuditLog()
    result = run_tick(
        brain,
        ToolRegistry([safe_tool, dangerous_tool]),
        Conscience(config.conscience.mode),
        Budget(config.heartbeat.max_steps_per_session),
        audit,
        context="Demonstration only; no external tools are available.",
    )
    output = {
        "text": result.response_text,
        "actions": [asdict(action) for action in result.actions],
        "stopped_reason": result.stopped_reason,
        "executions": {"record_note": safe_tool.calls, "delete_file": dangerous_tool.calls},
        "audit": [asdict(event) for event in audit.events],
    }
    print(json.dumps(output, default=str, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and run the offline demonstration."""
    parser = argparse.ArgumentParser(prog="aingel", description="Aingel agent framework")
    parser.add_argument("--config", type=Path, help="Optional TOML configuration file")
    parser.add_argument("--mode", choices=["sandbox", "supervised", "autonomous"])
    parser.add_argument("--max-steps", type=int, help="Override the per-session action budget")
    parser.add_argument("--demo", action="store_true", help="Run the offline safety demonstration")
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
        if not args.demo:
            parser.error("the initial release supports only --demo (offline; no real tools)")
        return _demo(config)
    except ValueError as error:
        print(f"aingel: {error}", file=sys.stderr)
        return 2
