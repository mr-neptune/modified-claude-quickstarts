from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

import sqlite3


@dataclass(frozen=True)
class Session:
    """Session metadata stored in the database."""

    id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SessionManager:
    """SQLite-backed session and chat history store."""

    def __init__(self, db_path: Path) -> None:
        self._lock = Lock()
        self._db_path = db_path
        self._initialize_db()

    def create(self) -> Session:
        """Create and persist a new session record."""
        session = Session(id=uuid4().hex)
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO sessions (id, created_at) VALUES (?, ?)",
                (session.id, session.created_at.isoformat()),
            )
            connection.commit()
        return session

    def get(self, session_id: str) -> Session | None:
        """Fetch a session by id, or None if not found."""
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT id, created_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return Session(id=row["id"], created_at=datetime.fromisoformat(row["created_at"]))

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Persist a chat message for a session."""
        created_at = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO chat_history (session_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                (session_id, role, content, created_at),
            )
            connection.commit()

    def list_messages(self, session_id: str) -> list[dict[str, str]]:
        """Return chat history as a list of dicts, ordered by insertion."""
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT role, content, created_at FROM chat_history "
                "WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        return [
            {
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def _initialize_db(self) -> None:
        """Create required tables if they do not exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS sessions ("
                "id TEXT PRIMARY KEY, "
                "created_at TEXT NOT NULL"
                ")"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS chat_history ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "session_id TEXT NOT NULL, "
                "role TEXT NOT NULL, "
                "content TEXT NOT NULL, "
                "created_at TEXT NOT NULL, "
                "FOREIGN KEY(session_id) REFERENCES sessions(id)"
                ")"
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection with row dict access."""
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection
