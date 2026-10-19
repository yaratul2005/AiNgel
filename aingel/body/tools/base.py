"""Tool contract shared by the body and conscience layers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class Risk(StrEnum):
    """Declared impact of running a tool."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class ToolSpec:
    """Public, model-facing description of a tool."""

    name: str
    description: str
    risk: Risk
    sandbox_safe: bool = False
    schema: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Tool name must be non-empty")
        if not isinstance(self.risk, Risk):
            raise ValueError("Tool risk must be a Risk value")
        if self.schema is not None and self.schema.get("type", "object") != "object":
            raise ValueError("Tool argument schema must describe an object")

    def as_dict(self) -> dict[str, object]:
        """Return a plain serializable description for a brain adapter."""
        return {
            "name": self.name,
            "description": self.description,
            "risk": self.risk.value,
            "parameters": self.schema or {"type": "object", "properties": {}},
        }


def validate_arguments(schema: dict[str, object] | None, args: object) -> str | None:
    """Validate a small JSON Schema subset and return an error when invalid."""
    if not isinstance(args, dict) or any(not isinstance(key, str) for key in args):
        return "tool arguments must be an object with string keys"
    if schema is None:
        return None

    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if (
        not isinstance(properties, dict)
        or not isinstance(required, list)
        or any(not isinstance(key, str) for key in required)
    ):
        return "tool argument schema is malformed"
    missing = set(required) - set(args)
    if missing:
        return f"missing required argument(s): {', '.join(sorted(missing))}"
    if schema.get("additionalProperties", False) is False:
        extra = set(args) - set(properties)
        if extra:
            return f"unknown argument(s): {', '.join(sorted(extra))}"

    type_map: dict[str, type | tuple[type, ...]] = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "object": dict,
        "array": list,
        "null": type(None),
    }
    for key, value in args.items():
        definition = properties.get(key)
        if not isinstance(definition, dict):
            continue
        expected = definition.get("type")
        accepted = type_map.get(expected) if isinstance(expected, str) else None
        if accepted is not None and (
            not isinstance(value, accepted)
            or (expected == "integer" and isinstance(value, bool))
        ):
            return f"argument {key!r} must be {expected}"
    return None


class Tool(Protocol):
    """A capability that may execute only after conscience approval."""

    spec: ToolSpec

    def run(self, **args: object) -> str:
        """Execute the operation and return its result."""
