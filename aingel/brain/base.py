"""Vendor-neutral interfaces for reasoning backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ToolCall:
    """A proposed call to a registered tool."""

    name: str
    args: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Response:
    """Text and tool calls returned by a brain."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class Brain(Protocol):
    """Interface implemented by any model or deterministic test brain."""

    def think(self, system: str, context: str, tools: list[dict[str, object]]) -> Response:
        """Return a response for the supplied context and tool descriptions."""
