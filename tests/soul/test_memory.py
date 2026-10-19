import sqlite3
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


def test_schema_v1_database_migrates_without_losing_memory(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute(
        """CREATE TABLE memories (
            id INTEGER PRIMARY KEY,
            kind TEXT NOT NULL,
            text TEXT NOT NULL,
            importance REAL NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    connection.execute(
        "INSERT INTO memories(kind, text, importance, created_at) VALUES (?, ?, ?, ?)",
        ("episodic", "legacy record", 0.5, "2026-01-01T00:00:00+00:00"),
    )
    connection.execute("PRAGMA user_version = 1")
    connection.commit()
    connection.close()

    with MemoryStore(database) as store:
        assert store.recall("legacy", k=1)[0].text == "legacy record"
        store.save_state("agenda", {"schema_version": 1})
        assert store.load_state("agenda") == {"schema_version": 1}

    connection = sqlite3.connect(database)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'agent_state'"
        ).fetchone() is not None
    finally:
        connection.close()
