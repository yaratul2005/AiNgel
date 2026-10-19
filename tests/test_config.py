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


def test_ollama_config_is_optional_and_validated() -> None:
    defaults = parse_config({})
    configured = parse_config(
        {
            "brain": {
                "provider": "ollama",
                "model": "llama3.2",
                "base_url": "http://localhost:11434",
                "timeout": 45,
            }
        }
    )

    assert defaults.brain.provider is None
    assert configured.brain.provider == "ollama"
    assert configured.brain.model == "llama3.2"
    assert configured.brain.timeout == 45


@pytest.mark.parametrize(
    "brain",
    [
        {"provider": "ollama"},
        {"provider": "other", "model": "model"},
        {"model": "llama3.2"},
        {"provider": "ollama", "model": "llama3.2", "base_url": "file:///tmp"},
        {"provider": "ollama", "model": "llama3.2", "timeout": float("inf")},
    ],
)
def test_invalid_brain_configuration_fails_clearly(brain: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        parse_config({"brain": brain})


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
