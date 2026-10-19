"""Bounded functional affect values updated by explicit event labels."""

from __future__ import annotations

import math
from dataclasses import dataclass


def clamp(value: float) -> float:
    """Clamp a finite numeric value to the inclusive range 0 through 1."""
    if not math.isfinite(value):
        raise ValueError("Affect values must be finite")
    return max(0.0, min(1.0, value))


@dataclass
class Affect:
    """Numeric state values that may influence context and policy choices."""

    hope: float = 0.5
    curiosity: float = 0.5
    frustration: float = 0.0
    trust: float = 0.5

    def __post_init__(self) -> None:
        for name in ("hope", "curiosity", "frustration", "trust"):
            setattr(self, name, clamp(getattr(self, name)))

    def update(self, event: str) -> None:
        """Apply a deterministic bounded change for a recognized event."""
        if event == "goal_progress":
            self.hope = clamp(self.hope + 0.10)
            self.frustration = clamp(self.frustration - 0.10)
        elif event == "tool_failure":
            self.frustration = clamp(self.frustration + 0.15)
            self.hope = clamp(self.hope - 0.05)
        elif event == "novel_input":
            self.curiosity = clamp(self.curiosity + 0.10)
        elif event == "reliable_outcome":
            self.trust = clamp(self.trust + 0.05)

    def decay(self, rate: float = 0.02) -> None:
        """Drift each state gently toward its neutral value."""
        if not math.isfinite(rate) or not 0.0 <= rate <= 1.0:
            raise ValueError("Affect decay rate must be between 0 and 1")
        for name, neutral in (
            ("hope", 0.5),
            ("curiosity", 0.5),
            ("frustration", 0.0),
            ("trust", 0.5),
        ):
            value = getattr(self, name)
            setattr(self, name, clamp(value + (neutral - value) * rate))

    def to_prompt(self) -> str:
        """Render bounded values for inclusion in agent context."""
        return (
            f"Functional state: hope={self.hope:.2f}, curiosity={self.curiosity:.2f}, "
            f"frustration={self.frustration:.2f}, trust={self.trust:.2f}"
        )
