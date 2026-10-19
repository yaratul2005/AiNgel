"""Append-only JSON Lines audit events with a minimal data footprint."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class AuditEvent:
    """One decision and outcome, excluding raw arguments and tool output."""

    timestamp: str
    tool_name: str
    verdict: str
    reason: str
    outcome: str


class AuditLog:
    """Keep events in memory and optionally append them to a JSONL file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._events: list[AuditEvent] = []

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        """Return an immutable snapshot of events recorded in this process."""
        return tuple(self._events)

    def record(self, tool_name: str, verdict: str, reason: str, outcome: str) -> AuditEvent:
        """Record a decision without persisting sensitive call arguments/results."""
        event = AuditEvent(
            timestamp=datetime.now(UTC).isoformat(),
            tool_name=tool_name,
            verdict=verdict,
            reason=reason,
            outcome=outcome,
        )
        self._events.append(event)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as audit_file:
                audit_file.write(json.dumps(asdict(event), sort_keys=True) + "\n")
                audit_file.flush()
        return event
