"""Build, save, and print sale receipts (SRS FR-5.1, FR-5.2).

``render_receipt`` is a pure function - given the sale data it returns the exact
text of the receipt, so it is easy to test. ``issue_receipt`` ties it together:
load the sale, render it, always save a copy to ``data_store/receipts/``, then
try to print. Printing failure never raises out of here - the result object
carries the outcome so the checkout screen can warn without blocking the sale.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from slp_pos import config
from slp_pos.data import sales_repo, users_repo
from slp_pos.hardware import printer
from slp_pos.hardware.printer import PrinterError

PrinterFn = Callable[[Path], None]


class ReceiptError(Exception):
    """The sale could not be found to build a receipt."""


@dataclass(frozen=True)
class ReceiptResult:
    sale_id: int
    text: str
    saved_path: Path
    printed: bool
    warning: str | None  # printer problem, if any


# --- rendering --------------------------------------------------------------


def _center(text: str, width: int) -> str:
    return text.center(width)


def _row(left: str, right: str, width: int) -> str:
    """Left text and right text on one line, right-aligned, left truncated."""
    space = width - len(right)
    if len(left) > space - 1:
        left = left[: max(space - 1, 0)].rstrip()
    return f"{left}{right:>{width - len(left)}}"


def _money(value: float) -> str:
    return f"{config.CURRENCY_SYMBOL}{value:,.2f}"


def render_receipt(
    sale: sales_repo.SaleRow,
    items: list[sales_repo.SaleItemRow],
    *,
    cashier_name: str,
    width: int | None = None,
) -> str:
    w = width or config.RECEIPT_WIDTH
    rule = "=" * w
    thin = "-" * w
    lines: list[str] = []

    lines.append(rule)
    lines.append(_center(config.STORE_NAME.upper(), w))
    if config.STORE_ADDRESS:
        lines.append(_center(config.STORE_ADDRESS, w))
    if config.STORE_PHONE:
        lines.append(_center(f"Tel: {config.STORE_PHONE}", w))
    lines.append(rule)

    lines.append(f"Receipt #: {sale.id:06d}")
    lines.append(f"Date     : {sale.sale_datetime.replace('T', ' ')}")
    lines.append(f"Cashier  : {cashier_name}")
    lines.append(thin)

    for item in items:
        lines.append(item.product_name[:w])
        qty_price = f"  {item.quantity} x {item.unit_price:,.2f}"
        lines.append(_row(qty_price, f"{item.line_total:,.2f}", w))

    lines.append(thin)
    lines.append(_row("TOTAL", _money(sale.total_amount), w))
    lines.append(_row(sale.payment_method.capitalize(), _money(sale.amount_tendered), w))
    lines.append(_row("Change", _money(sale.change_given), w))
    lines.append(rule)
    if config.RECEIPT_FOOTER:
        lines.append(_center(config.RECEIPT_FOOTER, w))
    lines.append(rule)

    return "\n".join(lines) + "\n"


# --- orchestration ---------------------------------------------------------


def _receipt_path(sale_id: int) -> Path:
    config.ensure_directories()
    return config.RECEIPT_DIR / f"receipt-{sale_id:06d}.txt"


def issue_receipt(
    conn: sqlite3.Connection,
    sale_id: int,
    *,
    printer_fn: PrinterFn | None = None,
) -> ReceiptResult:
    """Render, save, and (if enabled) print the receipt for a completed sale."""
    sale = sales_repo.get_sale(conn, sale_id)
    if sale is None:
        raise ReceiptError(f"Sale #{sale_id} was not found.")
    items = sales_repo.get_sale_items(conn, sale_id)
    user = users_repo.get_by_id(conn, sale.cashier_id)
    cashier_name = user.username if user else f"user {sale.cashier_id}"

    text = render_receipt(sale, items, cashier_name=cashier_name)

    path = _receipt_path(sale_id)
    path.write_text(text, encoding="utf-8")

    if not config.RECEIPT_PRINTING_ENABLED:
        return ReceiptResult(sale_id, text, path, printed=False, warning=None)

    send = printer_fn or printer.print_text_file
    try:
        send(path)
    except PrinterError as exc:
        return ReceiptResult(sale_id, text, path, printed=False, warning=str(exc))

    return ReceiptResult(sale_id, text, path, printed=True, warning=None)


def reprint_receipt(
    conn: sqlite3.Connection,
    sale_id: int,
    *,
    printer_fn: PrinterFn | None = None,
) -> ReceiptResult:
    """Re-issue a receipt for an existing sale (SRS FR-5.2)."""
    return issue_receipt(conn, sale_id, printer_fn=printer_fn)
