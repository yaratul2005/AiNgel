"""Identity and human-provided constitution loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Identity:
    """Stable agent name and optional human-authored constitution text."""

    name: str
    constitution: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Identity name must not be empty")

    def system_prompt(self) -> str:
        """Build a concise prompt from identity and supplied principles."""
        prompt = f"You are {self.name}."
        if self.constitution.strip():
            prompt += "\nHuman-reviewed principles:\n" + self.constitution.strip()
        return prompt


def load_identity(name: str, constitution_path: Path | None = None) -> Identity:
    """Load identity and optionally read an existing human-authored constitution."""
    constitution = ""
    if constitution_path is not None:
        try:
            constitution = constitution_path.read_text(encoding="utf-8")
        except OSError as error:
            raise ValueError(f"Could not read constitution at {constitution_path}: {error}") from error
    return Identity(name=name, constitution=constitution)
