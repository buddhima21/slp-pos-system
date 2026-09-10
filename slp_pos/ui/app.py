"""Main application window and screen router.

Phase 1 skeleton: opens a window and confirms the database initialised.
Later phases replace the placeholder with the Login screen, which then routes
to Checkout (cashier) or the full menu (admin).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from slp_pos import __version__, config
from slp_pos.db.migrate import migrate


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{config.STORE_NAME} POS")
        self.geometry("960x640")
        self.minsize(800, 560)

        # Set once login exists; every screen reads this for role checks.
        self.current_user: dict | None = None

        self._build_placeholder()

    def _build_placeholder(self) -> None:
        frame = ttk.Frame(self, padding=32)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=f"{config.STORE_NAME} POS",
            font=("Segoe UI", 26, "bold"),
        ).pack(pady=(24, 8))

        ttk.Label(
            frame,
            text=f"Version {__version__} — development skeleton",
            font=("Segoe UI", 11),
        ).pack()

        ttk.Separator(frame).pack(fill="x", pady=20)

        ttk.Label(
            frame,
            text=(
                "Phase 1 & 2 complete: window runs and the SQLite database is "
                "initialised.\n\n"
                f"Database file:\n{config.DB_PATH}\n\n"
                "Next: Phase 3 — Inventory screen (add / edit / search products)."
            ),
            font=("Segoe UI", 11),
            justify="left",
        ).pack(anchor="w")


def run() -> None:
    """Entry point: initialise the database, then start the UI loop."""
    config.ensure_directories()
    migrate()
    App().mainloop()
