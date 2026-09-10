"""Phase 2 checks: schema builds, default admin is seeded, migration is idempotent."""

from __future__ import annotations

from slp_pos.db.connection import get_connection
from slp_pos.db.migrate import migrate

EXPECTED_TABLES = {
    "products",
    "users",
    "sales",
    "sale_items",
    "stock_movements",
}


def _table_names(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {r["name"] for r in rows}


def test_all_tables_created(conn):
    assert EXPECTED_TABLES.issubset(_table_names(conn))


def test_default_admin_seeded(conn):
    row = conn.execute(
        "SELECT username, role FROM users WHERE username = 'admin'"
    ).fetchone()
    assert row is not None
    assert row["role"] == "admin"


def test_admin_password_is_hashed_not_plain(conn):
    row = conn.execute(
        "SELECT password_hash FROM users WHERE username = 'admin'"
    ).fetchone()
    assert row["password_hash"].startswith("pbkdf2_sha256$")
    assert "admin123" not in row["password_hash"]


def test_migrate_is_idempotent(db_path):
    migrate(db_path)  # second run
    migrate(db_path)  # third run
    conn = get_connection(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    finally:
        conn.close()
    assert count == 1  # no duplicate admin rows


def test_foreign_keys_enforced(conn):
    result = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert result == 1

    # sale_items.sale_id must reference a real sale
    try:
        conn.execute(
            "INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, line_total) "
            "VALUES (9999, 1, 1, 10.0, 10.0)"
        )
        raised = False
    except Exception:
        raised = True
    assert raised
