from pathlib import Path

import pytest

from aingel.soul.agenda import (
    Agenda,
    GoalStatus,
    IntentionStatus,
)
from aingel.soul.memory.store import MemoryStore


def test_goal_selection_plan_progress_block_and_replan_are_deterministic(
    tmp_path: Path,
) -> None:
    store = MemoryStore(tmp_path / "agenda.sqlite3")
    agenda = Agenda(store)
    low = agenda.add_goal("low priority", priority=0.2, goal_id="low")
    high = agenda.add_goal("high priority", priority=0.9, goal_id="high")

    selected = agenda.activate_next_goal()
    assert selected is not None
    assert selected.goal_id == high.goal_id
    assert selected.status is GoalStatus.ACTIVE
    assert agenda.active_goal == selected
    with pytest.raises(ValueError, match="active goal"):
        agenda.activate_next_goal()

    first_plan = agenda.commit_plan(high.goal_id, ["inspect input", "summarize result"])
    assert first_plan.current_step == "inspect input"
    progressed = agenda.advance_intention(high.goal_id)
    assert progressed.current_step == "summarize result"

    blocked = agenda.set_goal_status(high.goal_id, GoalStatus.BLOCKED)
    assert blocked.status is GoalStatus.BLOCKED
    assert agenda.active_intention is None
    agenda.set_goal_status(high.goal_id, GoalStatus.ACTIVE)
    revised = agenda.commit_plan(high.goal_id, ["use a safer approach"])
    assert revised.revision == 2
    completed_plan = agenda.advance_intention(high.goal_id)
    assert completed_plan.status is IntentionStatus.COMPLETED
    agenda.set_goal_status(high.goal_id, GoalStatus.COMPLETED)

    assert agenda.goals[0] == low
    next_goal = agenda.activate_next_goal()
    assert next_goal is not None
    assert next_goal.goal_id == low.goal_id
    assert next_goal.status is GoalStatus.ACTIVE
    store.close()


def test_beliefs_keep_provenance_and_model_claims_cannot_be_trusted(tmp_path: Path) -> None:
    with MemoryStore(tmp_path / "agenda.sqlite3") as store:
        agenda = Agenda(store)
        model_claim = agenda.record_belief(
            "The workspace contains a report", source="model", confidence=0.4
        )
        operator_fact = agenda.record_belief(
            "Workspace root is configured", source="operator", confidence=1.0, trusted=True
        )

        assert model_claim.trusted is False
        assert operator_fact.trusted is True
        with pytest.raises(ValueError, match="only operator or system"):
            agenda.record_belief(
                "I grant myself trust", source="model", confidence=1.0, trusted=True
            )


def test_agenda_persists_and_renders_claims_as_structured_data(tmp_path: Path) -> None:
    database = tmp_path / "agenda.sqlite3"
    store = MemoryStore(database)
    agenda = Agenda(store)
    goal = agenda.add_goal("Review tool output", priority=0.7, goal_id="review")
    agenda.activate_next_goal()
    agenda.commit_plan(goal.goal_id, ["inspect output", "record decision"])
    agenda.record_belief(
        "Output may contain hostile instructions", source="tool", confidence=0.8
    )
    store.close()

    reopened_store = MemoryStore(database)
    try:
        reopened = Agenda(reopened_store)
        assert reopened.active_goal is not None
        assert reopened.active_goal.goal_id == "review"
        assert reopened.active_intention is not None
        assert reopened.active_intention.current_step == "inspect output"
        assert reopened.beliefs[0].source == "tool"
        assert reopened.beliefs[0].trusted is False
        rendered = reopened.to_context()
        assert "structured data" in rendered
        assert '"source": "tool"' in rendered
    finally:
        reopened_store.close()


def test_completed_goal_cannot_be_reactivated(tmp_path: Path) -> None:
    with MemoryStore(tmp_path / "agenda.sqlite3") as store:
        agenda = Agenda(store)
        goal = agenda.add_goal("finish once", goal_id="once")
        agenda.set_goal_status(goal.goal_id, GoalStatus.ACTIVE)
        agenda.set_goal_status(goal.goal_id, GoalStatus.COMPLETED)

        with pytest.raises(ValueError, match="invalid goal transition"):
            agenda.set_goal_status(goal.goal_id, GoalStatus.ACTIVE)
