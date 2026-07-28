"""Second Brain: the owner's durable knowledge store.

Notes (decisions, supplier intel, customer preferences, design lessons) in
SQLite with FTS5 full-text search — local, no cloud service. This is owner
memory, not agent memory: it is exposed through the API for the owner, and
read-only to agents that hold the `brain.search` grant.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SecondBrain:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        with self._conn() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS notes (
                       id INTEGER PRIMARY KEY,
                       title TEXT NOT NULL,
                       body TEXT NOT NULL,
                       tags TEXT NOT NULL DEFAULT '',
                       created_at TEXT NOT NULL
                   )"""
            )
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5("
                "title, body, tags, content='notes', content_rowid='id')"
            )

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def add(self, title: str, body: str, tags: list[str] | None = None) -> int:
        tag_str = ",".join(tags or [])
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO notes (title, body, tags, created_at) VALUES (?,?,?,?)",
                (title, body, tag_str, datetime.now(timezone.utc).isoformat()),
            )
            note_id = cur.lastrowid
            conn.execute(
                "INSERT INTO notes_fts (rowid, title, body, tags) VALUES (?,?,?,?)",
                (note_id, title, body, tag_str),
            )
            return int(note_id)

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT n.id, n.title, n.tags, n.created_at,
                          snippet(notes_fts, 1, '[', ']', ' … ', 24) AS snippet
                   FROM notes_fts JOIN notes n ON n.id = notes_fts.rowid
                   WHERE notes_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (query, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get(self, note_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        return dict(row) if row else None

    def all(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, title, tags, created_at FROM notes ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
