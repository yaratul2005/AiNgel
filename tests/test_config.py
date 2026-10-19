import pytest

from aingel.config import load_config, parse_config


def test_defaults_are_sandbox_with_a_bounded_step_budget() -> None:
    config = parse_config({})

    assert config.conscience.mode == "sandbox"
    assert config.heartbeat.max_steps_per_session == 100
    assert config.body.workspace_root is None


def test_workspace_root_resolves_relative_to_config_file(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = tmp_path / "aingel.toml"
    config_path.write_text('[body]\nworkspace_root = "workspace"\n', encoding="utf-8")

    assert load_config(config_path).body.workspace_root == workspace.resolve()


@pytest.mark.parametrize(
    "data",
    [
        {"heartbeat": {"max_steps_per_session": True}},
        {"heartbeat": {"max_steps_per_session": 0}},
        {"conscience": {"mode": "unknown"}},
        {"body": {"workspace_root": ""}},
        {"body": {"workspace_root": True}},
        {"unexpected": {}},
    ],
)
def test_invalid_configuration_fails_clearly(data: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        parse_config(data)
