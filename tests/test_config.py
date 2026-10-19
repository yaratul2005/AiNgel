import pytest

from aingel.config import parse_config


def test_defaults_are_sandbox_with_a_bounded_step_budget() -> None:
    config = parse_config({})

    assert config.conscience.mode == "sandbox"
    assert config.heartbeat.max_steps_per_session == 100


@pytest.mark.parametrize(
    "data",
    [
        {"heartbeat": {"max_steps_per_session": True}},
        {"heartbeat": {"max_steps_per_session": 0}},
        {"conscience": {"mode": "unknown"}},
        {"unexpected": {}},
    ],
)
def test_invalid_configuration_fails_clearly(data: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        parse_config(data)
