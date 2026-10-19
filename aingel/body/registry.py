"""Registry of available body tools."""

from __future__ import annotations

from collections.abc import Iterable

from ..config import AgentConfig
from .tools.base import Tool
from .tools.workspace_read import WorkspaceReadTool


class ToolRegistry:
    """Store tools by unique name and expose model-facing specifications."""

    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            if not tool.spec.name or tool.spec.name in self._tools:
                raise ValueError(f"Tool names must be non-empty and unique: {tool.spec.name!r}")
            self._tools[tool.spec.name] = tool

    @classmethod
    def from_config(cls, config: AgentConfig, extra_tools: Iterable[Tool] = ()) -> ToolRegistry:
        """Build a registry, adding the workspace reader only when explicitly configured."""
        tools = list(extra_tools)
        if config.body.workspace_root is not None:
            try:
                tools.append(WorkspaceReadTool(config.body.workspace_root))
            except OSError as error:
                raise ValueError(
                    f"Could not open configured workspace root "
                    f"{config.body.workspace_root}: {error}"
                ) from error
        return cls(tools)

    def get(self, name: str) -> Tool | None:
        """Find a registered tool by name."""
        return self._tools.get(name)

    def specs(self) -> list[dict[str, object]]:
        """Return the descriptions of registered tools."""
        return [tool.spec.as_dict() for tool in self._tools.values()]
