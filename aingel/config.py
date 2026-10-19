"""Configuration loading and validation for the initial offline runtime."""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True)
class HeartbeatConfig:
    """Limits for one agent session."""

    max_steps_per_session: int = 100


@dataclass(frozen=True)
class ConscienceConfig:
    """Permission mode for proposed tool calls."""

    mode: str = "sandbox"


@dataclass(frozen=True)
class BodyConfig:
    """Explicitly enabled tool boundaries."""

    workspace_root: Path | None = None


@dataclass(frozen=True)
class BrainConfig:
    """Optional external reasoning backend settings."""

    provider: str | None = None
    model: str | None = None
    base_url: str = "http://localhost:11434"
    timeout: float = 30.0


@dataclass(frozen=True)
class StorageConfig:
    """Optional persistent paths for memory and action audit records."""

    database_path: Path | None = None
    audit_path: Path | None = None


@dataclass(frozen=True)
class AgentConfig:
    """Validated runtime configuration."""

    heartbeat: HeartbeatConfig = HeartbeatConfig()
    conscience: ConscienceConfig = ConscienceConfig()
    body: BodyConfig = BodyConfig()
    brain: BrainConfig = BrainConfig()
    storage: StorageConfig = StorageConfig()


def _section(data: dict[str, Any], name: str, allowed: set[str]) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise TypeError(f"Configuration section [{name}] must be a table")
    unknown = set(value) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"Unknown setting(s) in [{name}]: {names}")
    return value


def parse_config(data: dict[str, Any], *, base_dir: Path | None = None) -> AgentConfig:
    """Validate TOML-shaped data and return immutable settings."""
    if not isinstance(data, dict):
        raise TypeError("Configuration root must be a TOML table")
    unknown = set(data) - {"heartbeat", "conscience", "body", "brain", "storage"}
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

    body = _section(data, "body", {"workspace_root"})
    workspace_value = body.get("workspace_root")
    workspace_root: Path | None = None
    if workspace_value is not None:
        if not isinstance(workspace_value, str) or not workspace_value.strip():
            raise ValueError("body.workspace_root must be a non-empty path string")
        workspace_root = Path(workspace_value).expanduser()
        if not workspace_root.is_absolute() and base_dir is not None:
            workspace_root = base_dir / workspace_root
        workspace_root = workspace_root.resolve()

    brain = _section(data, "brain", {"provider", "model", "base_url", "timeout"})
    provider = brain.get("provider")
    model = brain.get("model")
    base_url = brain.get("base_url", "http://localhost:11434")
    timeout = brain.get("timeout", 30.0)
    if provider is None:
        if model is not None or "base_url" in brain or "timeout" in brain:
            raise ValueError("brain.provider = 'ollama' is required when brain settings are supplied")
    elif provider != "ollama":
        raise ValueError("brain.provider must be 'ollama'")
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ValueError("brain.model must be a non-empty string")
    if provider == "ollama" and model is None:
        raise ValueError("brain.model is required when brain.provider = 'ollama'")
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("brain.base_url must be a non-empty URL")
    parsed_brain_url = urlsplit(base_url.strip())
    if (
        parsed_brain_url.scheme not in {"http", "https"}
        or not parsed_brain_url.netloc
        or parsed_brain_url.username is not None
        or parsed_brain_url.password is not None
        or parsed_brain_url.query
        or parsed_brain_url.fragment
    ):
        raise ValueError("brain.base_url must be an http(s) URL without credentials or query")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError("brain.timeout must be a positive number of seconds")

    storage = _section(data, "storage", {"database_path", "audit_path"})

    def storage_path(setting: str) -> Path | None:
        value = storage.get(setting)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"storage.{setting} must be a non-empty path string")
        path = Path(value).expanduser()
        if not path.is_absolute() and base_dir is not None:
            path = base_dir / path
        return path.resolve()

    database_path = storage_path("database_path")
    audit_path = storage_path("audit_path")
    if database_path is not None and database_path == audit_path:
        raise ValueError("storage.database_path and storage.audit_path must be different files")

    return AgentConfig(
        HeartbeatConfig(max_steps),
        ConscienceConfig(mode),
        BodyConfig(workspace_root),
        BrainConfig(provider, model, base_url, float(timeout)),
        StorageConfig(database_path, audit_path),
    )


def load_config(path: Path) -> AgentConfig:
    """Load and validate a TOML configuration file."""
    try:
        with path.open("rb") as config_file:
            data = tomllib.load(config_file)
    except OSError as error:
        raise ValueError(f"Could not read config file {path}: {error}") from error
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"Invalid TOML in {path}: {error}") from error
    return parse_config(data, base_dir=path.expanduser().resolve().parent)
