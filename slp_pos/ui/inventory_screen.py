"""Inventory screen (SRS 6.3) - Admin adds, edits, and searches products.

Layout: a search bar on top, the product list (Treeview) on the left, and an
add/edit form on the right. Rows at or below their reorder level are tinted so
low stock is visible at a glance (SRS FR-1.4).

The screen never touches SQL. Each action runs inside
``db.connection.transaction`` and calls ``services.inventory_service``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from slp_pos.data import products_repo
from slp_pos.db.connection import transaction
from slp_pos.services import inventory_service
from slp_pos.services.inventory_service import InventoryError

_COLUMNS = (
    ("barcode", "Barcode", 130),
    ("name", "Name", 220),
    ("category", "Category", 120),
    ("cost_price", "Cost", 80),
    ("sale_price", "Price", 80),
    ("stock_qty", "Stock", 70),
    ("reorder_level", "Reorder", 70),
    ("status", "Status", 90),
)

_FORM_FIELDS = (
    ("barcode", "Barcode *"),
    ("name", "Name *"),
    ("category", "Category"),
    ("cost_price", "Cost price"),
    ("sale_price", "Sale price"),
    ("stock_qty", "Stock quantity"),
    ("reorder_level", "Reorder level"),
)


class InventoryScreen(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=12)
        self._selected_id: int | None = None
        self._show_inactive = tk.BooleanVar(value=False)
        self._vars: dict[str, tk.StringVar] = {
            key: tk.StringVar() for key, _ in _FORM_FIELDS
        }

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_search_bar()
        self._build_table()
        self._build_form()

        self.refresh()

    # --- construction -------------------------------------------------------

    def _build_search_bar(self) -> None:
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(bar, text="Search:").pack(side="left")
        self._search_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self._search_var, width=32)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda _e: self.refresh())

        ttk.Button(bar, text="Search", command=self.refresh).pack(side="left")
        ttk.Button(
            bar, text="Clear", command=self._clear_search
        ).pack(side="left", padx=(6, 0))
        ttk.Checkbutton(
            bar,
            text="Show inactive",
            variable=self._show_inactive,
            command=self.refresh,
        ).pack(side="left", padx=(16, 0))

        self._count_label = ttk.Label(bar, text="")
        self._count_label.pack(side="right")

    def _build_table(self) -> None:
        wrapper = ttk.Frame(self)
        wrapper.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)

        self._tree = ttk.Treeview(
            wrapper,
            columns=[c[0] for c in _COLUMNS],
            show="headings",
            selectmode="browse",
        )
        for key, heading, width in _COLUMNS:
            anchor = "e" if key in {"cost_price", "sale_price", "stock_qty", "reorder_level"} else "w"
            self._tree.heading(key, text=heading)
            self._tree.column(key, width=width, anchor=anchor, stretch=False)

        self._tree.tag_configure("low", background="#ffe0e0")
        self._tree.tag_configure("inactive", foreground="#999999")

        scroll = ttk.Scrollbar(wrapper, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        self._tree.bind("<<TreeviewSelect>>", self._on_row_selected)

    def _build_form(self) -> None:
        form = ttk.LabelFrame(self, text="Product details", padding=12)
        form.grid(row=1, column=1, sticky="ns")

        for row, (key, label) in enumerate(_FORM_FIELDS):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Entry(form, textvariable=self._vars[key], width=26).grid(
                row=row, column=1, pady=3, padx=(8, 0)
            )

        button_row = ttk.Frame(form)
        button_row.grid(row=len(_FORM_FIELDS), column=0, columnspan=2, pady=(12, 0))

        ttk.Button(button_row, text="New", command=self._start_new).grid(
            row=0, column=0, padx=3
        )
        ttk.Button(button_row, text="Save", command=self._save).grid(
            row=0, column=1, padx=3
        )
        self._toggle_button = ttk.Button(
            button_row, text="Deactivate", command=self._toggle_active
        )
        self._toggle_button.grid(row=0, column=2, padx=3)

        self._hint = ttk.Label(form, text="* required", foreground="#666666")
        self._hint.grid(row=len(_FORM_FIELDS) + 1, column=0, columnspan=2, pady=(8, 0))

    # --- data flow --------------------------------------------------------

    def refresh(self) -> None:
        term = self._search_var.get()
        with transaction() as conn:
            products = inventory_service.search_products(
                conn, term, include_inactive=self._show_inactive.get()
            )

        self._tree.delete(*self._tree.get_children())
        for product in products:
            tags: list[str] = []
            if not product.is_active:
                tags.append("inactive")
            elif product.is_low_stock:
                tags.append("low")
            self._tree.insert(
                "",
                "end",
                iid=str(product.id),
                values=(
                    product.barcode,
                    product.name,
                    product.category or "",
                    f"{product.cost_price:.2f}",
                    f"{product.sale_price:.2f}",
                    product.stock_qty,
                    product.reorder_level,
                    "Active" if product.is_active else "Inactive",
                ),
                tags=tags,
            )

        self._count_label.config(text=f"{len(products)} product(s)")
        if self._selected_id is not None and self._tree.exists(str(self._selected_id)):
            self._tree.selection_set(str(self._selected_id))
        else:
            self._start_new()

    def _on_row_selected(self, _event: object) -> None:
        selection = self._tree.selection()
        if not selection:
            return
        self._selected_id = int(selection[0])
        with transaction() as conn:
            product = products_repo.get_by_id(conn, self._selected_id)
        if product is None:
            return

        self._vars["barcode"].set(product.barcode)
        self._vars["name"].set(product.name)
        self._vars["category"].set(product.category or "")
        self._vars["cost_price"].set(f"{product.cost_price:.2f}")
        self._vars["sale_price"].set(f"{product.sale_price:.2f}")
        self._vars["stock_qty"].set(str(product.stock_qty))
        self._vars["reorder_level"].set(str(product.reorder_level))
        self._toggle_button.config(
            text="Reactivate" if not product.is_active else "Deactivate"
        )

    def _start_new(self) -> None:
        self._selected_id = None
        for key, _ in _FORM_FIELDS:
            self._vars[key].set("")
        for key in ("cost_price", "sale_price", "stock_qty", "reorder_level"):
            self._vars[key].set("0")
        self._toggle_button.config(text="Deactivate", state="disabled")
        if self._tree.selection():
            self._tree.selection_remove(self._tree.selection())

    # --- actions ---------------------------------------------------------

    def _collect(self) -> dict:
        return {key: self._vars[key].get() for key, _ in _FORM_FIELDS}

    def _save(self) -> None:
        data = self._collect()
        try:
            with transaction() as conn:
                if self._selected_id is None:
                    product = inventory_service.add_product(conn, **data)
                    action = "added"
                else:
                    product = inventory_service.update_product(
                        conn, self._selected_id, **data
                    )
                    action = "updated"
        except InventoryError as exc:
            messagebox.showerror("Cannot save product", str(exc), parent=self)
            return

        self._selected_id = product.id
        self.refresh()
        messagebox.showinfo("Saved", f"'{product.name}' {action}.", parent=self)

    def _toggle_active(self) -> None:
        if self._selected_id is None:
            return
        try:
            with transaction() as conn:
                current = products_repo.get_by_id(conn, self._selected_id)
                if current is None:
                    raise InventoryError("That product no longer exists.")
                if current.is_active:
                    inventory_service.deactivate_product(conn, self._selected_id)
                    verb = "deactivated"
                else:
                    inventory_service.reactivate_product(conn, self._selected_id)
                    verb = "reactivated"
        except InventoryError as exc:
            messagebox.showerror("Cannot update product", str(exc), parent=self)
            return

        self.refresh()
        messagebox.showinfo("Done", f"Product {verb}.", parent=self)

    def _clear_search(self) -> None:
        self._search_var.set("")
        self.refresh()
