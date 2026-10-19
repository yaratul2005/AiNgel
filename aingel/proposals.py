"""Typed, bounded proposals for non-policy agent state updates."""

from __future__ import annotations

from dataclasses import dataclass

MAX_PROPOSALS_PER_KIND = 10
MAX_PROPOSAL_TEXT_CHARS = 1_000


def _validate_text(value: str, label: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if not value.strip():
        raise ValueError(f"{label} must not be empty")
    if len(value) > MAX_PROPOSAL_TEXT_CHARS:
        raise ValueError(f"{label} exceeds {MAX_PROPOSAL_TEXT_CHARS} characters")


@dataclass(frozen=True)
class BeliefProposal:
    """A claim proposed for the agenda; it carries no trusted status."""

    content: str
    confidence: float

    def __post_init__(self) -> None:
        _validate_text(self.content, "belief proposal content")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not 0.0 <= self.confidence <= 1.0
        ):
            raise ValueError("belief proposal confidence must be between 0 and 1")


@dataclass(frozen=True)
class GoalProposal:
    """A proposed objective; accepting it can only create a pending goal."""

    description: str
    priority: float = 0.5

    def __post_init__(self) -> None:
        _validate_text(self.description, "goal proposal description")
        if (
            isinstance(self.priority, bool)
            or not isinstance(self.priority, (int, float))
            or not 0.0 <= self.priority <= 1.0
        ):
            raise ValueError("goal proposal priority must be between 0 and 1")


@dataclass(frozen=True)
class AgendaProposal:
    """An optional batch of bounded belief and goal proposals from a brain."""

    beliefs: tuple[BeliefProposal, ...] = ()
    goals: tuple[GoalProposal, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.beliefs, tuple) or not isinstance(self.goals, tuple):
            raise TypeError("agenda proposal collections must be tuples")
        if len(self.beliefs) > MAX_PROPOSALS_PER_KIND or len(self.goals) > MAX_PROPOSALS_PER_KIND:
            raise ValueError(f"at most {MAX_PROPOSALS_PER_KIND} proposals of each kind are allowed")
        if any(not isinstance(item, BeliefProposal) for item in self.beliefs):
            raise TypeError("agenda proposal beliefs must be BeliefProposal values")
        if any(not isinstance(item, GoalProposal) for item in self.goals):
            raise TypeError("agenda proposal goals must be GoalProposal values")


@dataclass(frozen=True)
class ProposalReceipt:
    """Identifiers of proposal items explicitly accepted by an application."""

    belief_ids: tuple[str, ...] = ()
    goal_ids: tuple[str, ...] = ()
