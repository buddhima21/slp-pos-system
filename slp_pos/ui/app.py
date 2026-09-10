"""Main application window and screen router.

Until Phase 8 adds Login and role-based routing, the window opens with both the
Checkout and Inventory tabs and runs as the default admin account. Phase 8
replaces this with a Login screen that sets ``current_user`` and shows only the
tabs that account's role allows.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from slp_pos import __version__, config
from slp_pos.data import users_repo
from slp_pos.db.connection import transaction
from slp_pos.db.migrate import migrate
from slp_pos.ui.checkout_screen import CheckoutScreen
from slp_pos.ui.inventory_screen import InventoryScreen


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{config.STORE_NAME} POS  -  v{__version__}")
        self.geometry("1120x720")
        self.minsize(960, 640)

        self.current_user = self._load_default_user()

        self._build_layout()

    def _load_default_user(self) -> dict:
        with transaction() as conn:
            admin = users_repo.get_first_active_admin(conn)
        if admin is None:  # migrate() guarantees one, but be explicit
            raise RuntimeError("No admin account found. Run the database migration.")
        return {"id": admin.id, "username": admin.username, "role": admin.role}

    def _build_layout(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        notebook.add(
            CheckoutScreen(notebook, cashier_id=self.current_user["id"]),
            text="Checkout",
        )
        notebook.add(InventoryScreen(notebook), text="Inventory")


def run() -> None:
    """Entry point: initialise the database, then start the UI loop."""
    config.ensure_directories()
    migrate()
    App().mainloop()
