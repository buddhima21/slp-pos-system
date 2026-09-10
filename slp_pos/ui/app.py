"""Main application window and screen router.

Until Phase 8 adds Login and role-based routing, the window opens straight to
the Inventory screen so the Phase 3 work can be used and tested. Checkout and
Reports screens are added in later phases and slotted into the same notebook.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from slp_pos import __version__, config
from slp_pos.db.migrate import migrate
from slp_pos.ui.inventory_screen import InventoryScreen


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{config.STORE_NAME} POS  -  v{__version__}")
        self.geometry("1040x680")
        self.minsize(900, 600)

        # Set once Login exists (Phase 8); screens read this for role checks.
        self.current_user: dict | None = None

        self._build_layout()

    def _build_layout(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        notebook.add(InventoryScreen(notebook), text="Inventory")

        placeholder = ttk.Frame(notebook, padding=32)
        ttk.Label(
            placeholder,
            text="Checkout screen arrives in Phase 4.",
            font=("Segoe UI", 12),
        ).pack(anchor="w")
        notebook.add(placeholder, text="Checkout")


def run() -> None:
    """Entry point: initialise the database, then start the UI loop."""
    config.ensure_directories()
    migrate()
    App().mainloop()
