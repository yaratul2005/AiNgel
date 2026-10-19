from pathlib import Path

import pytest

from aingel.soul.identity import Identity, load_identity


def test_identity_loads_human_provided_constitution(tmp_path: Path) -> None:
    constitution = tmp_path / "constitution.md"
    constitution.write_text("Be accurate and respect limits.", encoding="utf-8")

    identity = load_identity("Aingel", constitution)

    assert "You are Aingel." in identity.system_prompt()
    assert "Be accurate" in identity.system_prompt()


def test_identity_does_not_invent_missing_constitution() -> None:
    assert Identity("Aingel").constitution == ""


def test_missing_constitution_path_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Could not read constitution"):
        load_identity("Aingel", tmp_path / "missing.md")
