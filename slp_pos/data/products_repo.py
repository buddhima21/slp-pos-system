"""Data access for the ``products`` table (SRS 5.1).

Every function takes an open ``sqlite3.Connection`` and writes no ``COMMIT`` of
its own — the caller controls the transaction (see ``db.connection.transaction``).
This is the only module, together with the other ``*_repo`` modules, that
contains SQL for products.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

_COLUMNS = (
    "id, barcode, name, category, cost_price, sale_price, "
    "stock_qty, reorder_level, is_active"
)


@dataclass(frozen=True)
class Product:
    id: int
    barcode: str
    name: str
    category: str | None
    cost_price: float
    sale_price: float
    stock_qty: int
    reorder_level: int
    is_active: bool

    @property
    def is_low_stock(self) -> bool:
        return self.is_active and self.stock_qty <= self.reorder_level

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Product":
        return cls(
            id=row["id"],
            barcode=row["barcode"],
            name=row["name"],
            category=row["category"],
            cost_price=row["cost_price"],
            sale_price=row["sale_price"],
            stock_qty=row["stock_qty"],
            reorder_level=row["reorder_level"],
            is_active=bool(row["is_active"]),
        )


def get_by_id(conn: sqlite3.Connection, product_id: int) -> Product | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    return Product.from_row(row) if row else None


def get_by_barcode(conn: sqlite3.Connection, barcode: str) -> Product | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM products WHERE barcode = ?", (barcode.strip(),)
    ).fetchone()
    return Product.from_row(row) if row else None


def list_all(
    conn: sqlite3.Connection, *, include_inactive: bool = False
) -> list[Product]:
    sql = f"SELECT {_COLUMNS} FROM products"
    if not include_inactive:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY name COLLATE NOCASE"
    return [Product.from_row(r) for r in conn.execute(sql)]


def search(
    conn: sqlite3.Connection, term: str, *, include_inactive: bool = False
) -> list[Product]:
    """Match ``term`` against barcode (exact or partial) or name (partial)."""
    term = term.strip()
    if not term:
        return list_all(conn, include_inactive=include_inactive)

    like = f"%{term}%"
    sql = (
        f"SELECT {_COLUMNS} FROM products "
        "WHERE (barcode = ? OR barcode LIKE ? OR name LIKE ?)"
    )
    params: list[object] = [term, like, like]
    if not include_inactive:
        sql += " AND is_active = 1"
    sql += " ORDER BY name COLLATE NOCASE"
    return [Product.from_row(r) for r in conn.execute(sql, params)]


def list_low_stock(conn: sqlite3.Connection) -> list[Product]:
    """Active products at or below their reorder level (SRS FR-7.1)."""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM products "
        "WHERE is_active = 1 AND stock_qty <= reorder_level "
        "ORDER BY name COLLATE NOCASE"
    )
    return [Product.from_row(r) for r in rows]


def insert(
    conn: sqlite3.Connection,
    *,
    barcode: str,
    name: str,
    category: str | None,
    cost_price: float,
    sale_price: float,
    stock_qty: int,
    reorder_level: int,
) -> int:
    cur = conn.execute(
        "INSERT INTO products "
        "(barcode, name, category, cost_price, sale_price, stock_qty, reorder_level) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (barcode, name, category, cost_price, sale_price, stock_qty, reorder_level),
    )
    return int(cur.lastrowid)


def update(
    conn: sqlite3.Connection,
    product_id: int,
    *,
    barcode: str,
    name: str,
    category: str | None,
    cost_price: float,
    sale_price: float,
    stock_qty: int,
    reorder_level: int,
) -> None:
    conn.execute(
        "UPDATE products SET "
        "barcode = ?, name = ?, category = ?, cost_price = ?, sale_price = ?, "
        "stock_qty = ?, reorder_level = ? "
        "WHERE id = ?",
        (
            barcode,
            name,
            category,
            cost_price,
            sale_price,
            stock_qty,
            reorder_level,
            product_id,
        ),
    )


def set_active(conn: sqlite3.Connection, product_id: int, is_active: bool) -> None:
    conn.execute(
        "UPDATE products SET is_active = ? WHERE id = ?",
        (1 if is_active else 0, product_id),
    )


def adjust_stock(conn: sqlite3.Connection, product_id: int, delta: int) -> None:
    """Add ``delta`` (may be negative) to a product's stock quantity."""
    conn.execute(
        "UPDATE products SET stock_qty = stock_qty + ? WHERE id = ?",
        (delta, product_id),
    )
