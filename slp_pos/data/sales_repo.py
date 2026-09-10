"""Data access for the ``sales`` and ``sale_items`` tables (SRS 5.2 / 5.3).

Functions take an open connection and do not commit. A completed sale is
written as: one ``sales`` row, one ``sale_items`` row per line, and a stock
decrement per line - all inside a single ``transaction`` so it is atomic
(SRS FR-2.5).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class SaleRow:
    id: int
    sale_datetime: str
    cashier_id: int
    total_amount: float
    payment_method: str
    amount_tendered: float
    change_given: float

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "SaleRow":
        return cls(
            id=row["id"],
            sale_datetime=row["sale_datetime"],
            cashier_id=row["cashier_id"],
            total_amount=row["total_amount"],
            payment_method=row["payment_method"],
            amount_tendered=row["amount_tendered"],
            change_given=row["change_given"],
        )


@dataclass(frozen=True)
class SaleItemRow:
    id: int
    sale_id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    line_total: float


def insert_sale(
    conn: sqlite3.Connection,
    *,
    sale_datetime: str,
    cashier_id: int,
    total_amount: float,
    payment_method: str,
    amount_tendered: float,
    change_given: float,
) -> int:
    cur = conn.execute(
        "INSERT INTO sales "
        "(sale_datetime, cashier_id, total_amount, payment_method, "
        " amount_tendered, change_given) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            sale_datetime,
            cashier_id,
            total_amount,
            payment_method,
            amount_tendered,
            change_given,
        ),
    )
    return int(cur.lastrowid)


def insert_sale_item(
    conn: sqlite3.Connection,
    *,
    sale_id: int,
    product_id: int,
    quantity: int,
    unit_price: float,
    line_total: float,
) -> int:
    cur = conn.execute(
        "INSERT INTO sale_items "
        "(sale_id, product_id, quantity, unit_price, line_total) "
        "VALUES (?, ?, ?, ?, ?)",
        (sale_id, product_id, quantity, unit_price, line_total),
    )
    return int(cur.lastrowid)


def get_sale(conn: sqlite3.Connection, sale_id: int) -> SaleRow | None:
    row = conn.execute(
        "SELECT id, sale_datetime, cashier_id, total_amount, payment_method, "
        "       amount_tendered, change_given "
        "FROM sales WHERE id = ?",
        (sale_id,),
    ).fetchone()
    return SaleRow.from_row(row) if row else None


def get_sale_items(conn: sqlite3.Connection, sale_id: int) -> list[SaleItemRow]:
    rows = conn.execute(
        "SELECT si.id, si.sale_id, si.product_id, p.name AS product_name, "
        "       si.quantity, si.unit_price, si.line_total "
        "FROM sale_items si "
        "JOIN products p ON p.id = si.product_id "
        "WHERE si.sale_id = ? "
        "ORDER BY si.id",
        (sale_id,),
    )
    return [
        SaleItemRow(
            id=r["id"],
            sale_id=r["sale_id"],
            product_id=r["product_id"],
            product_name=r["product_name"],
            quantity=r["quantity"],
            unit_price=r["unit_price"],
            line_total=r["line_total"],
        )
        for r in rows
    ]


def count_sales(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0])
