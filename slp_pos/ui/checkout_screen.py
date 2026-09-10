"""Checkout screen (SRS 6.3) - the cashier's only screen.

Barcode-first workflow: the search box holds focus, the cashier types a name or
barcode and presses Enter. An exact barcode match is added straight to the sale;
otherwise the matches are listed to pick from. The running total is always
visible; entering the cash tendered shows the change due live.

No SQL here. Lookups and ``complete_sale`` run inside ``transaction``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from slp_pos import config
from slp_pos.data import products_repo
from slp_pos.db.connection import transaction
from slp_pos.services import checkout_service
from slp_pos.services.checkout_service import Cart, CheckoutError

_MONEY = config.CURRENCY_SYMBOL


def _money(value: float) -> str:
    return f"{_MONEY}{value:,.2f}"


class CheckoutScreen(ttk.Frame):
    def __init__(self, master: tk.Misc, cashier_id: int) -> None:
        super().__init__(master, padding=12)
        self._cashier_id = cashier_id
        self._cart = Cart()

        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)

        self._build_search()
        self._build_cart()
        self._build_payment()
        self._refresh_cart()
        self.after(100, lambda: self._search_entry.focus_set())

    # --- construction ----------------------------------------------------

    def _build_search(self) -> None:
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(bar, text="Scan or search:").pack(side="left")
        self._search_var = tk.StringVar()
        self._search_entry = ttk.Entry(bar, textvariable=self._search_var, width=36)
        self._search_entry.pack(side="left", padx=6)
        self._search_entry.bind("<Return>", self._on_search_enter)

        ttk.Button(bar, text="Search", command=self._run_search).pack(side="left")

        self._search_msg = ttk.Label(bar, text="", foreground="#b00000")
        self._search_msg.pack(side="left", padx=12)

    def _build_cart(self) -> None:
        left = ttk.Frame(self)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        left.rowconfigure(1, weight=3)
        left.rowconfigure(3, weight=1)
        left.columnconfigure(0, weight=1)

        ttk.Label(left, text="Current sale", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, sticky="w"
        )

        self._cart_tree = ttk.Treeview(
            left,
            columns=("name", "qty", "unit", "total"),
            show="headings",
            selectmode="browse",
        )
        for key, heading, width, anchor in (
            ("name", "Item", 240, "w"),
            ("qty", "Qty", 60, "center"),
            ("unit", "Unit", 100, "e"),
            ("total", "Line total", 110, "e"),
        ):
            self._cart_tree.heading(key, text=heading)
            self._cart_tree.column(key, width=width, anchor=anchor, stretch=False)
        self._cart_tree.tag_configure("over", background="#ffe0e0")
        self._cart_tree.grid(row=1, column=0, sticky="nsew", pady=(4, 6))

        controls = ttk.Frame(left)
        controls.grid(row=2, column=0, sticky="w")
        ttk.Button(controls, text="- Qty", command=lambda: self._bump(-1)).pack(side="left")
        ttk.Button(controls, text="+ Qty", command=lambda: self._bump(1)).pack(side="left", padx=4)
        ttk.Button(controls, text="Remove line", command=self._remove_line).pack(side="left", padx=4)
        ttk.Button(controls, text="Clear sale", command=self._clear_sale).pack(side="left", padx=4)

        ttk.Label(left, text="Search results (double-click to add)").grid(
            row=3, column=0, sticky="sw", pady=(10, 2)
        )
        self._results_tree = ttk.Treeview(
            left,
            columns=("barcode", "name", "price", "stock"),
            show="headings",
            selectmode="browse",
            height=5,
        )
        for key, heading, width, anchor in (
            ("barcode", "Barcode", 130, "w"),
            ("name", "Name", 220, "w"),
            ("price", "Price", 100, "e"),
            ("stock", "Stock", 70, "e"),
        ):
            self._results_tree.heading(key, text=heading)
            self._results_tree.column(key, width=width, anchor=anchor, stretch=False)
        self._results_tree.grid(row=4, column=0, sticky="nsew")
        self._results_tree.bind("<Double-1>", self._add_selected_result)
        self._results_tree.bind("<Return>", self._add_selected_result)

    def _build_payment(self) -> None:
        right = ttk.LabelFrame(self, text="Payment", padding=16)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        self._total_label = ttk.Label(right, text=_money(0), font=("Segoe UI", 28, "bold"))
        self._total_label.grid(row=0, column=0, sticky="w")
        ttk.Label(right, text="Total due").grid(row=1, column=0, sticky="w", pady=(0, 16))

        ttk.Label(right, text="Cash tendered").grid(row=2, column=0, sticky="w")
        self._tendered_var = tk.StringVar()
        tendered_entry = ttk.Entry(
            right, textvariable=self._tendered_var, font=("Segoe UI", 14), width=16
        )
        tendered_entry.grid(row=3, column=0, sticky="w", pady=(2, 12))
        tendered_entry.bind("<KeyRelease>", lambda _e: self._update_change())
        tendered_entry.bind("<Return>", lambda _e: self._complete_sale())

        self._change_label = ttk.Label(right, text="Change: -", font=("Segoe UI", 16))
        self._change_label.grid(row=4, column=0, sticky="w", pady=(0, 20))

        self._complete_btn = ttk.Button(
            right, text="Complete sale  (F12)", command=self._complete_sale
        )
        self._complete_btn.grid(row=5, column=0, sticky="ew", ipady=8)
        self.winfo_toplevel().bind("<F12>", lambda _e: self._complete_sale())

    # --- search / add --------------------------------------------------

    def _on_search_enter(self, _event: object) -> None:
        term = self._search_var.get().strip()
        if not term:
            return
        # Exact barcode -> add immediately (scanner-style).
        with transaction() as conn:
            exact = products_repo.get_by_barcode(conn, term)
        if exact and exact.is_active:
            self._add_product(exact.id)
            self._search_var.set("")
            self._clear_results()
            return
        self._run_search()

    def _run_search(self) -> None:
        term = self._search_var.get().strip()
        self._search_msg.config(text="")
        with transaction() as conn:
            matches = products_repo.search(conn, term)
        self._clear_results()
        for product in matches:
            self._results_tree.insert(
                "",
                "end",
                iid=str(product.id),
                values=(
                    product.barcode,
                    product.name,
                    _money(product.sale_price),
                    product.stock_qty,
                ),
            )
        if not matches:
            self._search_msg.config(text=f'No product found for "{term}".')

    def _add_selected_result(self, _event: object) -> None:
        selection = self._results_tree.selection()
        if selection:
            self._add_product(int(selection[0]))

    def _add_product(self, product_id: int) -> None:
        try:
            with transaction() as conn:
                checkout_service.add_to_cart(conn, self._cart, product_id)
        except CheckoutError as exc:
            messagebox.showerror("Cannot add item", str(exc), parent=self)
            return
        self._refresh_cart()
        self._search_entry.focus_set()

    # --- cart edits ---------------------------------------------------

    def _selected_cart_product_id(self) -> int | None:
        selection = self._cart_tree.selection()
        return int(selection[0]) if selection else None

    def _bump(self, delta: int) -> None:
        product_id = self._selected_cart_product_id()
        if product_id is None:
            return
        line = self._cart.get(product_id)
        if line is None:
            return
        try:
            self._cart.set_quantity(product_id, line.quantity + delta)
        except CheckoutError as exc:
            messagebox.showerror("Cannot change quantity", str(exc), parent=self)
        self._refresh_cart()

    def _remove_line(self) -> None:
        product_id = self._selected_cart_product_id()
        if product_id is not None:
            self._cart.remove(product_id)
            self._refresh_cart()

    def _clear_sale(self) -> None:
        if self._cart.is_empty:
            return
        if messagebox.askyesno("Clear sale", "Remove all items from this sale?", parent=self):
            self._cart.clear()
            self._tendered_var.set("")
            self._refresh_cart()

    # --- display -----------------------------------------------------

    def _refresh_cart(self) -> None:
        self._cart_tree.delete(*self._cart_tree.get_children())
        for line in self._cart.lines:
            self._cart_tree.insert(
                "",
                "end",
                iid=str(line.product_id),
                values=(
                    line.name,
                    line.quantity,
                    _money(line.unit_price),
                    _money(line.line_total),
                ),
                tags=("over",) if line.exceeds_stock else (),
            )
        self._total_label.config(text=_money(self._cart.total))
        self._update_change()

    def _update_change(self) -> None:
        raw = self._tendered_var.get().strip()
        if not raw:
            self._change_label.config(text="Change: -", foreground="black")
            return
        try:
            change = checkout_service.change_due(self._cart.total, raw)
        except CheckoutError as exc:
            self._change_label.config(text=str(exc), foreground="#b00000")
            return
        self._change_label.config(text=f"Change: {_money(change)}", foreground="#0a7a0a")

    def _clear_results(self) -> None:
        self._results_tree.delete(*self._results_tree.get_children())

    # --- complete --------------------------------------------------

    def _complete_sale(self) -> None:
        if self._cart.is_empty:
            messagebox.showinfo("Nothing to sell", "Add at least one item first.", parent=self)
            return
        try:
            with transaction() as conn:
                sale = checkout_service.complete_sale(
                    conn,
                    self._cart,
                    cashier_id=self._cashier_id,
                    amount_tendered=self._tendered_var.get(),
                )
        except CheckoutError as exc:
            messagebox.showerror("Sale not completed", str(exc), parent=self)
            return

        messagebox.showinfo(
            "Sale complete",
            f"Sale #{sale.sale_id}\n"
            f"Total: {_money(sale.total)}\n"
            f"Tendered: {_money(sale.amount_tendered)}\n"
            f"Change: {_money(sale.change_given)}\n\n"
            "(Receipt printing is added in Phase 7.)",
            parent=self,
        )
        self._tendered_var.set("")
        self._clear_results()
        self._search_var.set("")
        self._refresh_cart()
        self._search_entry.focus_set()
