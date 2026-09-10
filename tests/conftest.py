"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from slp_pos.db.connection import get_connection
from slp_pos.db.migrate import migrate


@pytest.fixture()
def db_path(tmp_path):
    """A fresh, migrated database file for one test."""
    path = tmp_path / "test_slp_pos.db"
    migrate(path)
    return path


@pytest.fixture()
def conn(db_path):
    """An open connection to the fresh test database."""
    connection = get_connection(db_path)
    try:
        yield connection
    finally:
        connection.close()
