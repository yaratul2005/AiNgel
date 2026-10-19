import pytest

from aingel.soul.affect import Affect


def test_affect_updates_are_bounded_and_decay_toward_neutral() -> None:
    affect = Affect(hope=0.99, frustration=0.02)
    affect.update("goal_progress")
    assert affect.hope == 1.0
    assert affect.frustration == 0.0

    affect.update("tool_failure")
    before = affect.frustration
    affect.decay(rate=0.5)
    assert 0.0 <= affect.frustration < before
    assert affect.hope < 1.0


def test_affect_rejects_non_finite_values_and_invalid_decay() -> None:
    with pytest.raises(ValueError):
        Affect(hope=float("nan"))
    with pytest.raises(ValueError):
        Affect().decay(rate=2.0)
