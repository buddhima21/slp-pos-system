"""Create the database schema and seed a default admin account.

Idempotent: safe to run on every application startup. Deleting the .db file
and re-running rebuilds it from scratch.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from slp_pos import config
from slp_pos.db.connection import get_connection
from slp_pos.services.auth_service import hash_password


def _load_schema_sql() -> str:
    return resources.files("slp_pos.db").joinpath("schema.sql").read_text(encoding="utf-8")


def migrate(db_path: str | Path | None = None) -> None:
    """Apply the schema and ensure at least one admin user exists."""
    conn = get_connection(db_path)
    try:
        conn.executescript(_load_schema_sql())

        row = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        if row["n"] == 0:
            conn.execute(
                "INSERT INTO users (username, password_hash, role) "
                "VALUES (?, ?, 'admin')",
                (
                    config.DEFAULT_ADMIN_USERNAME,
                    hash_password(config.DEFAULT_ADMIN_PASSWORD),
                ),
            )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
    print(f"Database ready at {config.DB_PATH}")
