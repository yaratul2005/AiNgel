"""Deterministic SQLite memory with recency and keyword recall."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

MEMORY_KINDS = {"episodic", "semantic", "reflective"}
SCHEMA_VERSION = 2


@dataclass(frozen=True)
class Memory:
    """One persisted memory record."""

    id: int
    kind: str
    text: str
    importance: float
    created_at: str


class MemoryStore:
    """Store and recall memories in a SQLite database."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path) if str(path) != ":memory:" else ":memory:"
        if isinstance(self.path, Path):
            self.path.parent.mkdir(parents=True, exist_ok=True)
            database: str | Path = self.path
        else:
            database = self.path
        self._connection = sqlite3.connect(database)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError(f"Memory database version {version} is newer than supported")
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY,
                kind TEXT NOT NULL CHECK (kind IN ('episodic', 'semantic', 'reflective')),
                text TEXT NOT NULL,
                importance REAL NOT NULL CHECK (importance >= 0 AND importance <= 1),
                created_at TEXT NOT NULL
            )"""
        )
        self._connection.execute("CREATE INDEX IF NOT EXISTS memories_created_at ON memories(id)")
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS agent_state (
                state_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        self._connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._connection.commit()

    def add(self, kind: str, text: str, importance: float = 0.5) -> int:
        """Persist a memory and return its stable row identifier."""
        if kind not in MEMORY_KINDS:
            raise ValueError(f"kind must be one of: {', '.join(sorted(MEMORY_KINDS))}")
        if not text.strip():
            raise ValueError("Memory text must not be empty")
        if not 0.0 <= importance <= 1.0:
            raise ValueError("importance must be between 0 and 1")
        created_at = datetime.now(UTC).isoformat()
        cursor = self._connection.execute(
            "INSERT INTO memories(kind, text, importance, created_at) VALUES (?, ?, ?, ?)",
            (kind, text, importance, created_at),
        )
        self._connection.commit()
        return int(cursor.lastrowid)

    def recall(self, query: str, k: int = 5) -> list[Memory]:
        """Rank keyword matches first, then importance and recency deterministically."""
        if k < 0:
            raise ValueError("k must not be negative")
        if k == 0:
            return []
        rows = self._connection.execute("SELECT * FROM memories ORDER BY id DESC").fetchall()
        terms = set(re.findall(r"\w+", query.casefold()))

        def ranking(row: sqlite3.Row) -> tuple[int, float, int]:
            words = set(re.findall(r"\w+", row["text"].casefold()))
            matches = len(terms & words)
            return (-matches, -row["importance"], -row["id"])

        ranked = sorted(rows, key=ranking)[:k]
        return [Memory(row["id"], row["kind"], row["text"], row["importance"], row["created_at"]) for row in ranked]

    def summarize_recent(self, n: int = 50) -> str:
        """Return the latest n records as a compact chronological digest."""
        if n < 0:
            raise ValueError("n must not be negative")
        rows = self._connection.execute(
            "SELECT kind, text FROM memories ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        return "\n".join(f"[{row['kind']}] {row['text']}" for row in reversed(rows))

    def save_state(self, state_key: str, payload: dict[str, object]) -> None:
        """Atomically replace one versioned structured state snapshot."""
        if not state_key.strip():
            raise ValueError("state_key must not be empty")
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self._connection.execute(
            """INSERT INTO agent_state(state_key, payload, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(state_key) DO UPDATE SET
                   payload = excluded.payload,
                   updated_at = excluded.updated_at""",
            (state_key, serialized, datetime.now(UTC).isoformat()),
        )
        self._connection.commit()

    def load_state(self, state_key: str) -> dict[str, object] | None:
        """Load one structured snapshot, rejecting corrupt or non-object payloads."""
        row = self._connection.execute(
            "SELECT payload FROM agent_state WHERE state_key = ?", (state_key,)
        ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Stored state {state_key!r} is not valid JSON") from error
        if not isinstance(payload, dict):
            raise RuntimeError(  # noqa: TRY004 - malformed persisted state is a storage error
                f"Stored state {state_key!r} must be a JSON object"
            )
        return payload

    def close(self) -> None:
        """Close the underlying database connection."""
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
