"""Configuration loading and validation for the initial offline runtime."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HeartbeatConfig:
    """Limits for one agent session."""

    max_steps_per_session: int = 100


@dataclass(frozen=True)
class ConscienceConfig:
    """Permission mode for proposed tool calls."""

    mode: str = "sandbox"


@dataclass(frozen=True)
class AgentConfig:
    """Validated runtime configuration."""

    heartbeat: HeartbeatConfig = HeartbeatConfig()
    conscience: ConscienceConfig = ConscienceConfig()


def _section(data: dict[str, Any], name: str, allowed: set[str]) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"Configuration section [{name}] must be a table")
    unknown = set(value) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"Unknown setting(s) in [{name}]: {names}")
    return value


def parse_config(data: dict[str, Any]) -> AgentConfig:
    """Validate TOML-shaped data and return immutable settings."""
    if not isinstance(data, dict):
        raise ValueError("Configuration root must be a TOML table")
    unknown = set(data) - {"heartbeat", "conscience"}
    if unknown:
        raise ValueError(f"Unknown top-level setting(s): {', '.join(sorted(unknown))}")

    heartbeat = _section(data, "heartbeat", {"max_steps_per_session"})
    max_steps = heartbeat.get("max_steps_per_session", 100)
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
        raise ValueError("heartbeat.max_steps_per_session must be a positive integer")

    conscience = _section(data, "conscience", {"mode"})
    mode = conscience.get("mode", "sandbox")
    if not isinstance(mode, str) or mode not in {"sandbox", "supervised", "autonomous"}:
        raise ValueError("conscience.mode must be sandbox, supervised, or autonomous")
    return AgentConfig(HeartbeatConfig(max_steps), ConscienceConfig(mode))


def load_config(path: Path) -> AgentConfig:
    """Load and validate a TOML configuration file."""
    try:
        with path.open("rb") as config_file:
            data = tomllib.load(config_file)
    except OSError as error:
        raise ValueError(f"Could not read config file {path}: {error}") from error
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"Invalid TOML in {path}: {error}") from error
    return parse_config(data)
