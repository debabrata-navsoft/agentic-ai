"""SQLite persistence: users and login tokens, plus each user's chat sessions (full API
message history), long-term notes, and RAG document metadata."""

import hashlib
import json
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user',
    disabled      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_tokens (
    token_hash  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS password_resets (
    token_hash  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);
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
CREATE TABLE IF NOT EXISTS agents (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    name         TEXT NOT NULL,
    role         TEXT NOT NULL DEFAULT '',
    icon         TEXT NOT NULL DEFAULT 'bot',
    description  TEXT NOT NULL DEFAULT '',
    instructions TEXT NOT NULL DEFAULT '',
    tools        TEXT NOT NULL DEFAULT '[]',
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS agents_user ON agents (user_id);
CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    size        INTEGER NOT NULL,
    chunks      INTEGER NOT NULL,
    created_at  TEXT NOT NULL
);
"""

# Tables whose rows belong to a user. Databases created before accounts existed lack the
# column; their rows keep user_id NULL until the first account signs up and claims them.
OWNED_TABLES = ("sessions", "notes", "documents")

USER_FIELDS = ("id", "email", "name", "role", "disabled", "created_at")
USER_COLUMNS = ", ".join(USER_FIELDS)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash_token(token: str) -> str:
    # Only a hash is stored, so a leaked database doesn't hand out live logins.
    return hashlib.sha256(token.encode()).hexdigest()


def _user(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return None if row is None else {**dict(row), "disabled": bool(row["disabled"])}


AGENT_FIELDS = ("name", "role", "icon", "description", "instructions", "tools")
AGENT_COLUMNS = "id, " + ", ".join(AGENT_FIELDS) + ", created_at"


def _agent(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return None if row is None else {**dict(row), "tools": json.loads(row["tools"])}


def _agent_values(fields: dict[str, Any]) -> list[Any]:
    return [json.dumps(fields[f]) if f == "tools" else fields[f] for f in AGENT_FIELDS]


class Store:
    def __init__(self, db_path: Path | str):
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._lock = threading.Lock()

    def _migrate(self) -> None:
        for table in OWNED_TABLES:
            columns = {r["name"] for r in self._conn.execute(f"PRAGMA table_info({table})")}
            if "user_id" not in columns:
                self._conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT")
            self._conn.execute(f"CREATE INDEX IF NOT EXISTS {table}_user ON {table} (user_id)")
        # The agent a chat runs as; NULL (older chats, or a deleted agent) means plain Synora.
        if "agent_id" not in {r["name"] for r in self._conn.execute("PRAGMA table_info(sessions)")}:
            self._conn.execute("ALTER TABLE sessions ADD COLUMN agent_id TEXT")
        self._conn.commit()

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    # ---- users ----------------------------------------------------------

    def create_user(self, email: str, name: str, password_hash: str) -> dict[str, Any]:
        """Create an account. The first account becomes admin and takes over pre-account data.

        Raises sqlite3.IntegrityError if the email is already registered.
        """
        user_id = uuid.uuid4().hex
        now = _now()
        with self._lock:
            try:
                first = self._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
                role = "admin" if first else "user"
                self._conn.execute(
                    "INSERT INTO users (id, email, name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, email, name, password_hash, role, now),
                )
                if first:
                    for table in OWNED_TABLES:
                        self._conn.execute(f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL", (user_id,))
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return {"id": user_id, "email": email, "name": name, "role": role, "disabled": False, "created_at": now}

    def get_user_credentials(self, email: str) -> dict[str, Any] | None:
        """The user row including password_hash, for checking a login."""
        row = self._execute(f"SELECT {USER_COLUMNS}, password_hash FROM users WHERE email = ?", (email,)).fetchone()
        return _user(row)

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        return _user(self._execute(f"SELECT {USER_COLUMNS} FROM users WHERE id = ?", (user_id,)).fetchone())

    def list_users(self) -> list[dict[str, Any]]:
        rows = self._execute(f"SELECT {USER_COLUMNS} FROM users ORDER BY created_at").fetchall()
        return [_user(r) for r in rows]

    def update_user(self, user_id: str, *, role: str | None = None, disabled: bool | None = None) -> dict[str, Any] | None:
        if role is not None:
            self._execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        if disabled is not None:
            self._execute("UPDATE users SET disabled = ? WHERE id = ?", (int(disabled), user_id))
            if disabled:
                self.delete_user_tokens(user_id)
        return self.get_user(user_id)

    # ---- login tokens ---------------------------------------------------

    def create_token(self, user_id: str, ttl: timedelta) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        created, expires = now.isoformat(timespec="seconds"), (now + ttl).isoformat(timespec="seconds")
        self._execute("DELETE FROM auth_tokens WHERE expires_at < ?", (created,))  # prune expired logins
        self._execute(
            "INSERT INTO auth_tokens (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (_hash_token(token), user_id, created, expires),
        )
        return token

    def get_user_by_token(self, token: str) -> dict[str, Any] | None:
        """The active (not disabled) user for an unexpired token, else None."""
        row = self._execute(
            f"SELECT {', '.join(f'u.{c}' for c in USER_FIELDS)} FROM auth_tokens t "
            "JOIN users u ON u.id = t.user_id WHERE t.token_hash = ? AND t.expires_at > ? AND u.disabled = 0",
            (_hash_token(token), _now()),
        ).fetchone()
        return _user(row)

    def delete_token(self, token: str) -> None:
        self._execute("DELETE FROM auth_tokens WHERE token_hash = ?", (_hash_token(token),))

    def delete_user_tokens(self, user_id: str, keep: str | None = None) -> None:
        """Sign the user out everywhere, except the login `keep` (the current one) if given."""
        keep_hash = _hash_token(keep) if keep else ""
        self._execute("DELETE FROM auth_tokens WHERE user_id = ? AND token_hash != ?", (user_id, keep_hash))

    def set_password(self, user_id: str, password_hash: str, keep_token: str | None = None) -> None:
        """Change the password and sign the user out everywhere except `keep_token`."""
        self._execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
        self.delete_user_tokens(user_id, keep=keep_token)

    # ---- password reset tokens (single use; only the hash is stored) ----

    def create_reset_token(self, user_id: str, ttl: timedelta) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        # One live link per user: a new request replaces the old one (and expired ones go too).
        self._execute(
            "DELETE FROM password_resets WHERE user_id = ? OR expires_at < ?",
            (user_id, now.isoformat(timespec="seconds")),
        )
        self._execute(
            "INSERT INTO password_resets (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (_hash_token(token), user_id, (now + ttl).isoformat(timespec="seconds")),
        )
        return token

    def use_reset_token(self, token: str) -> str | None:
        """Consume a reset token: the user ID if it was valid and unexpired, else None."""
        with self._lock:
            row = self._conn.execute(
                "DELETE FROM password_resets WHERE token_hash = ? RETURNING user_id, expires_at",
                (_hash_token(token),),
            ).fetchone()
            self._conn.commit()
        return row["user_id"] if row and row["expires_at"] > _now() else None

    # ---- sessions -------------------------------------------------------

    def create_session(self, user_id: str, title: str = "New chat", agent_id: str | None = None) -> dict[str, Any]:
        session_id = uuid.uuid4().hex
        now = _now()
        self._execute(
            "INSERT INTO sessions (id, user_id, title, agent_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, user_id, title, agent_id, now, now),
        )
        return {"id": session_id, "title": title, "agent_id": agent_id, "created_at": now, "updated_at": now}

    def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        rows = self._execute(
            "SELECT id, title, agent_id, created_at, updated_at FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_session(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        row = self._execute(
            "SELECT id, title, agent_id, created_at, updated_at, messages FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
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

    def rename_session(self, user_id: str, session_id: str, title: str) -> bool:
        return self._execute(
            "UPDATE sessions SET title = ? WHERE id = ? AND user_id = ?", (title, session_id, user_id)
        ).rowcount > 0

    def delete_session(self, user_id: str, session_id: str) -> bool:
        return self._execute("DELETE FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id)).rowcount > 0

    # ---- agents (per-user profiles: instructions + allowed tools) ---------

    def list_agents(self, user_id: str) -> list[dict[str, Any]]:
        rows = self._execute(
            f"SELECT {AGENT_COLUMNS} FROM agents WHERE user_id = ? ORDER BY created_at, rowid", (user_id,)
        ).fetchall()
        return [_agent(r) for r in rows]

    def get_agent(self, user_id: str, agent_id: str) -> dict[str, Any] | None:
        row = self._execute(
            f"SELECT {AGENT_COLUMNS} FROM agents WHERE id = ? AND user_id = ?", (agent_id, user_id)
        ).fetchone()
        return _agent(row)

    def create_agent(self, user_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        agent_id = uuid.uuid4().hex
        self._execute(
            f"INSERT INTO agents ({AGENT_COLUMNS}, user_id) VALUES (?, {', '.join('?' * len(AGENT_FIELDS))}, ?, ?)",
            (agent_id, *_agent_values(fields), _now(), user_id),
        )
        return self.get_agent(user_id, agent_id)

    def seed_agents(self, user_id: str, presets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Give a user their own editable copies of the built-in agents."""
        for preset in presets:
            self.create_agent(user_id, preset)
        return self.list_agents(user_id)

    def update_agent(self, user_id: str, agent_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        self._execute(
            f"UPDATE agents SET {', '.join(f'{f} = ?' for f in AGENT_FIELDS)} WHERE id = ? AND user_id = ?",
            (*_agent_values(fields), agent_id, user_id),
        )
        return self.get_agent(user_id, agent_id)

    def delete_agent(self, user_id: str, agent_id: str) -> bool:
        return self._execute("DELETE FROM agents WHERE id = ? AND user_id = ?", (agent_id, user_id)).rowcount > 0

    # ---- notes (long-term memory shared across a user's sessions) -------

    def add_note(self, user_id: str, title: str, content: str, tags: list[str]) -> dict[str, Any]:
        now = _now()
        cur = self._execute(
            "INSERT INTO notes (user_id, title, content, tags, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, title, content, ",".join(tags), now),
        )
        return {"id": cur.lastrowid, "title": title, "content": content, "tags": tags, "created_at": now}

    def search_notes(self, user_id: str, query: str = "", limit: int = 20) -> list[dict[str, Any]]:
        like = f"%{query}%"  # an empty query matches every note
        rows = self._execute(
            "SELECT id, title, content, tags, created_at FROM notes "
            "WHERE user_id = ? AND (title LIKE ? OR content LIKE ? OR tags LIKE ?) ORDER BY id DESC LIMIT ?",
            (user_id, like, like, like, limit),
        ).fetchall()
        return [{**dict(r), "tags": [t for t in r["tags"].split(",") if t]} for r in rows]

    def delete_note(self, user_id: str, note_id: int) -> bool:
        return self._execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id)).rowcount > 0

    # ---- RAG documents (metadata only; chunks live in the vector DB) -----

    def add_document(self, user_id: str, name: str, size: int, chunks: int) -> dict[str, Any]:
        doc = {"id": uuid.uuid4().hex, "name": name, "size": size, "chunks": chunks, "created_at": _now()}
        self._execute(
            "INSERT INTO documents (id, user_id, name, size, chunks, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (doc["id"], user_id, name, size, chunks, doc["created_at"]),
        )
        return doc

    def list_documents(self, user_id: str) -> list[dict[str, Any]]:
        rows = self._execute(
            "SELECT id, name, size, chunks, created_at FROM documents WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_document(self, user_id: str, doc_id: str) -> bool:
        return self._execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id)).rowcount > 0
