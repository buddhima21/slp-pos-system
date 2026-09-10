"""Checkout / sale processing (SRS FR-2.1 - FR-2.5).

``Cart`` is a plain in-memory object - no database, no Tkinter. The service
functions look products up, apply the rules (stock checks, tendered vs total),
and write a completed sale.

Atomicity (SRS FR-2.5): ``complete_sale`` performs every write - the sale row,
each sale item, each stock decrement - on the connection it is given. The
caller runs it inside ``db.connection.transaction``, so any failure rolls the
whole sale back and nothing is half-recorded.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

from slp_pos.data import products_repo, sales_repo
from slp_pos.data.products_repo import Product
from slp_pos.services.parsing import parse_money

PAYMENT_CASH = "cash"

# v1.0 accepts cash only. The column and this tuple are the single place to add
# card / mobile later (SRS FR-4.2, 10.3).
SUPPORTED_PAYMENT_METHODS: tuple[str, ...] = (PAYMENT_CASH,)


class CheckoutError(Exception):
    """A sale could not be built or completed. Message is shown to the cashier."""


@dataclass
class CartLine:
    product_id: int
    barcode: str
    name: str
    unit_price: float
    quantity: int
    stock_available: int  # snapshot from the last lookup, for UI warnings

    @property
    def line_total(self) -> float:
        return round(self.unit_price * self.quantity, 2)

    @property
    def exceeds_stock(self) -> bool:
        return self.quantity > self.stock_available


@dataclass
class Cart:
    _lines: dict[int, CartLine] = field(default_factory=dict)

    # --- reads ---------------------------------------------------------
    @property
    def lines(self) -> list[CartLine]:
        return list(self._lines.values())

    @property
    def is_empty(self) -> bool:
        return not self._lines

    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self._lines.values())

    @property
    def subtotal(self) -> float:
        return round(sum(line.line_total for line in self._lines.values()), 2)

    @property
    def total(self) -> float:
        # No tax or discounts in v1.0; kept separate so it is easy to extend.
        return self.subtotal

    def get(self, product_id: int) -> CartLine | None:
        return self._lines.get(product_id)

    # --- writes -------------------------------------------------------
    def add_product(self, product: Product, quantity: int = 1) -> CartLine:
        if quantity <= 0:
            raise CheckoutError("Quantity must be at least 1.")
        existing = self._lines.get(product.id)
        if existing:
            existing.quantity += quantity
            existing.unit_price = product.sale_price
            existing.stock_available = product.stock_qty
            return existing
        line = CartLine(
            product_id=product.id,
            barcode=product.barcode,
            name=product.name,
            unit_price=product.sale_price,
            quantity=quantity,
            stock_available=product.stock_qty,
        )
        self._lines[product.id] = line
        return line

    def set_quantity(self, product_id: int, quantity: int) -> None:
        line = self._lines.get(product_id)
        if line is None:
            raise CheckoutError("That item is not in the current sale.")
        if quantity <= 0:
            del self._lines[product_id]
        else:
            line.quantity = quantity

    def remove(self, product_id: int) -> None:
        self._lines.pop(product_id, None)

    def clear(self) -> None:
        self._lines.clear()


@dataclass(frozen=True)
class CompletedSale:
    sale_id: int
    sale_datetime: str
    cashier_id: int
    payment_method: str
    total: float
    amount_tendered: float
    change_given: float
    lines: tuple[CartLine, ...]


# --- operations -------------------------------------------------------------


def add_to_cart(
    conn: sqlite3.Connection,
    cart: Cart,
    product_id: int,
    quantity: int = 1,
) -> CartLine:
    """Add a product to the sale by id (SRS FR-2.1)."""
    product = products_repo.get_by_id(conn, product_id)
    if product is None or not product.is_active:
        raise CheckoutError("That product is not available for sale.")
    return cart.add_product(product, quantity)


def add_by_barcode(
    conn: sqlite3.Connection, cart: Cart, barcode: str, quantity: int = 1
) -> CartLine:
    """Add a product to the sale by exact barcode (used by the scanner, FR-3)."""
    product = products_repo.get_by_barcode(conn, barcode)
    if product is None or not product.is_active:
        raise CheckoutError(f"No product found for barcode {barcode.strip()}.")
    return cart.add_product(product, quantity)


@dataclass(frozen=True)
class TenderResult:
    """Outcome of checking a cash amount against the sale total (SRS FR-4.1)."""

    ok: bool
    tendered: float | None  # parsed amount, or None if it was not a number
    change: float           # >= 0 when ok
    shortfall: float        # > 0 when the tender does not cover the total
    message: str            # reason, when not ok


def evaluate_tender(total: float, amount_tendered: object) -> TenderResult:
    """Work out change or shortfall for a tender without raising."""
    try:
        tendered = parse_money(amount_tendered, "Amount tendered")
    except ValueError as exc:
        return TenderResult(False, None, 0.0, 0.0, str(exc))
    if tendered + 1e-9 < total:
        return TenderResult(
            ok=False,
            tendered=tendered,
            change=0.0,
            shortfall=round(total - tendered, 2),
            message=(
                f"Amount tendered ({tendered:.2f}) is less than the total ({total:.2f})."
            ),
        )
    return TenderResult(True, tendered, round(tendered - total, 2), 0.0, "")


def change_due(total: float, amount_tendered: object) -> float:
    """Change for a given tender, or raise if it does not cover the total."""
    result = evaluate_tender(total, amount_tendered)
    if not result.ok:
        raise CheckoutError(result.message)
    return result.change


def normalize_payment_method(payment_method: str) -> str:
    """Lower-case and validate a payment method against what v1.0 supports."""
    method = (payment_method or "").strip().lower()
    if method not in SUPPORTED_PAYMENT_METHODS:
        raise CheckoutError(f"Unsupported payment method: {payment_method!r}.")
    return method


def complete_sale(
    conn: sqlite3.Connection,
    cart: Cart,
    *,
    cashier_id: int,
    amount_tendered: object,
    payment_method: str = PAYMENT_CASH,
    sale_datetime: str | None = None,
) -> CompletedSale:
    """Record the sale permanently (SRS FR-2.5). Run inside a transaction."""
    if cart.is_empty:
        raise CheckoutError("Add at least one item before completing the sale.")

    method = normalize_payment_method(payment_method)
    total = cart.total
    tender = evaluate_tender(total, amount_tendered)
    if not tender.ok:
        raise CheckoutError(tender.message)
    tendered = tender.tendered
    change = tender.change

    # Authoritative stock re-check against current data, inside the transaction.
    shortages: list[str] = []
    for line in cart.lines:
        product = products_repo.get_by_id(conn, line.product_id)
        if product is None or not product.is_active:
            raise CheckoutError(f"'{line.name}' is no longer available.")
        if line.quantity > product.stock_qty:
            shortages.append(
                f"  {product.name}: {product.stock_qty} in stock, "
                f"{line.quantity} requested"
            )
    if shortages:
        raise CheckoutError("Not enough stock to complete this sale:\n" + "\n".join(shortages))

    when = sale_datetime or datetime.now().isoformat(timespec="seconds")
    sale_id = sales_repo.insert_sale(
        conn,
        sale_datetime=when,
        cashier_id=cashier_id,
        total_amount=total,
        payment_method=method,
        amount_tendered=tendered,
        change_given=change,
    )
    for line in cart.lines:
        sales_repo.insert_sale_item(
            conn,
            sale_id=sale_id,
            product_id=line.product_id,
            quantity=line.quantity,
            unit_price=line.unit_price,
            line_total=line.line_total,
        )
        products_repo.adjust_stock(conn, line.product_id, -line.quantity)

    completed = CompletedSale(
        sale_id=sale_id,
        sale_datetime=when,
        cashier_id=cashier_id,
        payment_method=method,
        total=total,
        amount_tendered=tendered,
        change_given=change,
        lines=tuple(cart.lines),
    )
    cart.clear()
    return completed
