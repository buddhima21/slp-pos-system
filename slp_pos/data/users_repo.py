"""Data access for the ``users`` table (SRS 5.4).

Minimal for now - Phase 8 (login / roles) extends this. ``password_hash`` is
only read by the auth flow; the UI works with :class:`UserRow`, which omits it.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class UserRow:
    id: int
    username: str
    role: str
    is_active: bool

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "UserRow":
        return cls(
            id=row["id"],
            username=row["username"],
            role=row["role"],
            is_active=bool(row["is_active"]),
        )


def get_by_id(conn: sqlite3.Connection, user_id: int) -> UserRow | None:
    row = conn.execute(
        "SELECT id, username, role, is_active FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return UserRow.from_row(row) if row else None


def get_by_username(conn: sqlite3.Connection, username: str) -> UserRow | None:
    row = conn.execute(
        "SELECT id, username, role, is_active FROM users WHERE username = ?",
        (username.strip(),),
    ).fetchone()
    return UserRow.from_row(row) if row else None


def get_password_hash(conn: sqlite3.Connection, username: str) -> str | None:
    row = conn.execute(
        "SELECT password_hash FROM users WHERE username = ? AND is_active = 1",
        (username.strip(),),
    ).fetchone()
    return row["password_hash"] if row else None


def get_first_active_admin(conn: sqlite3.Connection) -> UserRow | None:
    row = conn.execute(
        "SELECT id, username, role, is_active FROM users "
        "WHERE role = 'admin' AND is_active = 1 ORDER BY id LIMIT 1"
    ).fetchone()
    return UserRow.from_row(row) if row else None
