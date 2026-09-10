"""Application-wide configuration and filesystem paths.

Paths are resolved relative to the executable when frozen by PyInstaller,
and relative to the project root otherwise. This keeps the live database and
backups *next to* the .exe on the store PC rather than inside it.
"""

from __future__ import annotations

import sys
from pathlib import Path

STORE_NAME = "SLP Supermarket"

# Default credentials created on first run. Must be changed before go-live.
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"

# Backup policy (SRS FR-9.1 / Section 10.2): keep a week of rotating copies.
BACKUP_RETENTION_DAYS = 7


def _app_base_dir() -> Path:
    """Folder that holds the app; data_store/ and backups/ sit alongside it."""
    if getattr(sys, "frozen", False):  # running as a PyInstaller bundle
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_BASE_DIR: Path = _app_base_dir()
DATA_DIR: Path = APP_BASE_DIR / "data_store"
BACKUP_DIR: Path = APP_BASE_DIR / "backups"
DB_PATH: Path = DATA_DIR / "slp_pos.db"


def ensure_directories() -> None:
    """Create the runtime folders if they do not exist yet."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
