"""SQLite persistence for chat sessions (full API message history) and long-term notes."""

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    messages    TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    size        INTEGER NOT NULL,
    chunks      INTEGER NOT NULL,
    created_at  TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, db_path: Path | str):
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    # ---- sessions -------------------------------------------------------

    def create_session(self, title: str = "New chat") -> dict[str, Any]:
        session_id = uuid.uuid4().hex
        now = _now()
        self._execute(
            "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (session_id, title, now, now),
        )
        return {"id": session_id, "title": title, "created_at": now, "updated_at": now}

    def list_sessions(self) -> list[dict[str, Any]]:
        rows = self._execute(
            "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self._execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["messages"] = json.loads(data["messages"])
        return data

    def save_messages(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        self._execute(
            "UPDATE sessions SET messages = ?, updated_at = ? WHERE id = ?",
            (json.dumps(messages), _now(), session_id),
        )

    def rename_session(self, session_id: str, title: str) -> bool:
        return self._execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id)).rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        return self._execute("DELETE FROM sessions WHERE id = ?", (session_id,)).rowcount > 0

    # ---- notes (long-term memory shared across sessions) ----------------

    def add_note(self, title: str, content: str, tags: list[str]) -> dict[str, Any]:
        now = _now()
        cur = self._execute(
            "INSERT INTO notes (title, content, tags, created_at) VALUES (?, ?, ?, ?)",
            (title, content, ",".join(tags), now),
        )
        return {"id": cur.lastrowid, "title": title, "content": content, "tags": tags, "created_at": now}

    def search_notes(self, query: str = "", limit: int = 20) -> list[dict[str, Any]]:
        like = f"%{query}%"  # an empty query matches every note
        rows = self._execute(
            "SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? OR tags LIKE ? ORDER BY id DESC LIMIT ?",
            (like, like, like, limit),
        ).fetchall()
        return [{**dict(r), "tags": [t for t in r["tags"].split(",") if t]} for r in rows]

    def delete_note(self, note_id: int) -> bool:
        return self._execute("DELETE FROM notes WHERE id = ?", (note_id,)).rowcount > 0

    # ---- RAG documents (metadata only; chunks live in the vector DB) -----

    def add_document(self, name: str, size: int, chunks: int) -> dict[str, Any]:
        doc = {"id": uuid.uuid4().hex, "name": name, "size": size, "chunks": chunks, "created_at": _now()}
        self._execute(
            "INSERT INTO documents (id, name, size, chunks, created_at) VALUES (?, ?, ?, ?, ?)",
            tuple(doc.values()),
        )
        return doc

    def list_documents(self) -> list[dict[str, Any]]:
        rows = self._execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def delete_document(self, doc_id: str) -> bool:
        return self._execute("DELETE FROM documents WHERE id = ?", (doc_id,)).rowcount > 0
