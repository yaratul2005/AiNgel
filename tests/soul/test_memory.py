from pathlib import Path

import pytest

from aingel.soul.memory.store import MemoryStore


def test_memory_recall_is_deterministic_and_survives_reopen(tmp_path: Path) -> None:
    database = tmp_path / "memories.sqlite3"
    store = MemoryStore(database)
    store.add("episodic", "Fetched a page about model safety", importance=0.8)
    store.add("semantic", "Model safety needs an allowlist", importance=0.9)
    store.add("episodic", "A timer fired", importance=0.2)
    assert store.recall("model safety", k=2)[0].text == "Model safety needs an allowlist"
    store.close()

    reopened = MemoryStore(database)
    try:
        assert len(reopened.recall("", k=10)) == 3
        assert "[episodic] A timer fired" in reopened.summarize_recent(n=1)
    finally:
        reopened.close()


def test_memory_rejects_invalid_records_and_limits(tmp_path: Path) -> None:
    with MemoryStore(tmp_path / "memory.sqlite3") as store:
        with pytest.raises(ValueError):
            store.add("other", "text")
        with pytest.raises(ValueError):
            store.add("episodic", " ")
        with pytest.raises(ValueError):
            store.recall("query", k=-1)
