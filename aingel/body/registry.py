"""Registry of available body tools."""

from __future__ import annotations

from collections.abc import Iterable

from .tools.base import Tool


class ToolRegistry:
    """Store tools by unique name and expose model-facing specifications."""

    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            if not tool.spec.name or tool.spec.name in self._tools:
                raise ValueError(f"Tool names must be non-empty and unique: {tool.spec.name!r}")
            self._tools[tool.spec.name] = tool

    def get(self, name: str) -> Tool | None:
        """Find a registered tool by name."""
        return self._tools.get(name)

    def specs(self) -> list[dict[str, object]]:
        """Return the descriptions of registered tools."""
        return [tool.spec.as_dict() for tool in self._tools.values()]
