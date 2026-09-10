"""SQLite connection factory.

Every connection is opened in WAL mode with foreign keys enforced. WAL mode
is the main safeguard against database corruption from an abrupt shutdown
mid-write (SRS reliability requirement, Section 4 / 10.2).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from slp_pos import config


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection to the POS database.

    Args:
        db_path: Override the database file (used by tests). Defaults to
            ``config.DB_PATH``.
    """
    if db_path is None:
        config.ensure_directories()
        db_path = config.DB_PATH

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn
