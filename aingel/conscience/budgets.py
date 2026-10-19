"""Session action budget."""

from dataclasses import dataclass


@dataclass
class Budget:
    """Count attempted actions so denials cannot be used to evade limits."""

    max_steps: int
    steps_used: int = 0

    @property
    def exhausted(self) -> bool:
        """Whether the session has reached its action limit."""
        return self.steps_used >= self.max_steps

    def consume(self) -> bool:
        """Charge one proposed action, returning false when already exhausted."""
        if self.exhausted:
            return False
        self.steps_used += 1
        return True
