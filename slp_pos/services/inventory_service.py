"""Business rules for product & inventory management (SRS FR-1.1 - FR-1.4).

No SQL and no Tkinter here. Functions take an open connection, validate input,
enforce the rules (barcode required and unique, no negative prices or stock),
and delegate persistence to ``data.products_repo``.

Raises ``InventoryError`` with a human-readable, multi-line message that the
UI can show directly in a dialog.
"""

from __future__ import annotations

import sqlite3

from slp_pos.data import products_repo
from slp_pos.data.products_repo import Product

NAME_MAX_LENGTH = 120
CATEGORY_MAX_LENGTH = 60


class InventoryError(Exception):
    """Validation or rule violation while managing products."""


def _to_money(value: object, label: str) -> float:
    try:
        number = round(float(str(value).strip()), 2)
    except (TypeError, ValueError):
        raise InventoryError(f"{label} must be a number.")
    if number < 0:
        raise InventoryError(f"{label} cannot be negative.")
    return number


def _to_count(value: object, label: str) -> int:
    try:
        text = str(value).strip()
        number = int(text)
    except (TypeError, ValueError):
        raise InventoryError(f"{label} must be a whole number.")
    if number < 0:
        raise InventoryError(f"{label} cannot be negative.")
    return number


def _clean_fields(
    *,
    barcode: object,
    name: object,
    category: object,
    cost_price: object,
    sale_price: object,
    stock_qty: object,
    reorder_level: object,
) -> dict:
    errors: list[str] = []

    barcode_clean = str(barcode or "").strip()
    name_clean = str(name or "").strip()
    category_clean = str(category or "").strip() or None

    if not barcode_clean:
        errors.append("Barcode is required.")
    if not name_clean:
        errors.append("Name is required.")
    elif len(name_clean) > NAME_MAX_LENGTH:
        errors.append(f"Name must be {NAME_MAX_LENGTH} characters or fewer.")
    if category_clean and len(category_clean) > CATEGORY_MAX_LENGTH:
        errors.append(f"Category must be {CATEGORY_MAX_LENGTH} characters or fewer.")

    values: dict = {}
    for key, raw, label, parser in (
        ("cost_price", cost_price, "Cost price", _to_money),
        ("sale_price", sale_price, "Sale price", _to_money),
        ("stock_qty", stock_qty, "Stock quantity", _to_count),
        ("reorder_level", reorder_level, "Reorder level", _to_count),
    ):
        try:
            values[key] = parser(raw, label)
        except InventoryError as exc:
            errors.append(str(exc))

    if errors:
        raise InventoryError("\n".join(errors))

    values["barcode"] = barcode_clean
    values["name"] = name_clean
    values["category"] = category_clean
    return values


def _require_unique_barcode(
    conn: sqlite3.Connection, barcode: str, *, exclude_id: int | None = None
) -> None:
    existing = products_repo.get_by_barcode(conn, barcode)
    if existing and existing.id != exclude_id:
        raise InventoryError(
            f"Barcode {barcode} is already used by '{existing.name}'."
        )


# --- Public API ---------------------------------------------------------------


def add_product(
    conn: sqlite3.Connection,
    *,
    barcode: str,
    name: str,
    category: str | None = None,
    cost_price: object = 0,
    sale_price: object = 0,
    stock_qty: object = 0,
    reorder_level: object = 0,
) -> Product:
    """Create a product (SRS FR-1.1). Returns the stored record."""
    fields = _clean_fields(
        barcode=barcode,
        name=name,
        category=category,
        cost_price=cost_price,
        sale_price=sale_price,
        stock_qty=stock_qty,
        reorder_level=reorder_level,
    )
    _require_unique_barcode(conn, fields["barcode"])
    new_id = products_repo.insert(conn, **fields)
    created = products_repo.get_by_id(conn, new_id)
    assert created is not None
    return created


def update_product(
    conn: sqlite3.Connection,
    product_id: int,
    *,
    barcode: str,
    name: str,
    category: str | None = None,
    cost_price: object = 0,
    sale_price: object = 0,
    stock_qty: object = 0,
    reorder_level: object = 0,
) -> Product:
    """Edit an existing product (SRS FR-1.2)."""
    if products_repo.get_by_id(conn, product_id) is None:
        raise InventoryError("That product no longer exists.")

    fields = _clean_fields(
        barcode=barcode,
        name=name,
        category=category,
        cost_price=cost_price,
        sale_price=sale_price,
        stock_qty=stock_qty,
        reorder_level=reorder_level,
    )
    _require_unique_barcode(conn, fields["barcode"], exclude_id=product_id)
    products_repo.update(conn, product_id, **fields)
    updated = products_repo.get_by_id(conn, product_id)
    assert updated is not None
    return updated


def deactivate_product(conn: sqlite3.Connection, product_id: int) -> None:
    """Soft-delete a product (SRS FR-1.2). Sales history is preserved."""
    if products_repo.get_by_id(conn, product_id) is None:
        raise InventoryError("That product no longer exists.")
    products_repo.set_active(conn, product_id, False)


def reactivate_product(conn: sqlite3.Connection, product_id: int) -> None:
    if products_repo.get_by_id(conn, product_id) is None:
        raise InventoryError("That product no longer exists.")
    products_repo.set_active(conn, product_id, True)


def search_products(
    conn: sqlite3.Connection, term: str = "", *, include_inactive: bool = False
) -> list[Product]:
    """Search by name or barcode (SRS FR-1.3). Blank term returns everything."""
    return products_repo.search(conn, term, include_inactive=include_inactive)


def get_low_stock_products(conn: sqlite3.Connection) -> list[Product]:
    """Products at or below their reorder level (SRS FR-1.4 / FR-7.1)."""
    return products_repo.list_low_stock(conn)
