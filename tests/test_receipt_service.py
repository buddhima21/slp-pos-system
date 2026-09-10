"""Phase 7 checks: receipt rendering, saving, and print-failure handling
(SRS FR-5.1, FR-5.2, and the 'printer disconnected' scenario in 9.1)."""

from __future__ import annotations

import pytest

from slp_pos import config
from slp_pos.data import products_repo
from slp_pos.hardware.printer import PrinterError
from slp_pos.services import checkout_service, receipt_service
from slp_pos.services.checkout_service import Cart
from slp_pos.services.receipt_service import ReceiptError

CASHIER_ID = 1


@pytest.fixture(autouse=True)
def receipts_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RECEIPT_DIR", tmp_path / "receipts")
    monkeypatch.setattr(config, "RECEIPT_PRINTING_ENABLED", True)


def _make_sale(conn):
    bread = products_repo.get_by_id(
        conn,
        products_repo.insert(
            conn, barcode="1", name="White Bread 450g", category=None,
            cost_price=90, sale_price=130, stock_qty=40, reorder_level=5,
        ),
    )
    milk = products_repo.get_by_id(
        conn,
        products_repo.insert(
            conn, barcode="2", name="Fresh Milk 1L", category=None,
            cost_price=210, sale_price=280, stock_qty=25, reorder_level=5,
        ),
    )
    cart = Cart()
    cart.add_product(bread, 2)
    cart.add_product(milk, 1)
    return checkout_service.complete_sale(
        conn, cart, cashier_id=CASHIER_ID, amount_tendered="1000"
    )


def test_render_receipt_contents(conn):
    sale = _make_sale(conn)
    result = receipt_service.issue_receipt(conn, sale.sale_id, printer_fn=lambda _p: None)
    text = result.text

    assert config.STORE_NAME.upper() in text
    assert f"{sale.sale_id:06d}" in text
    assert "White Bread 450g" in text
    assert "Fresh Milk 1L" in text
    assert "2 x 130.00" in text
    assert "TOTAL" in text
    assert "Change" in text
    assert config.RECEIPT_FOOTER in text
    # every line fits the configured width
    assert all(len(line) <= config.RECEIPT_WIDTH for line in text.splitlines())


def test_issue_receipt_saves_file(conn):
    sale = _make_sale(conn)
    result = receipt_service.issue_receipt(conn, sale.sale_id, printer_fn=lambda _p: None)
    assert result.saved_path.exists()
    assert result.saved_path.read_text(encoding="utf-8") == result.text
    assert result.printed is True
    assert result.warning is None


def test_printer_failure_does_not_raise(conn):
    """Printer disconnected -> receipt still saved, warning returned, no crash."""
    sale = _make_sale(conn)

    def broken_printer(_path):
        raise PrinterError("Printer is offline.")

    result = receipt_service.issue_receipt(
        conn, sale.sale_id, printer_fn=broken_printer
    )
    assert result.printed is False
    assert "offline" in result.warning
    assert result.saved_path.exists()  # copy is kept regardless


def test_printing_disabled(conn, monkeypatch):
    monkeypatch.setattr(config, "RECEIPT_PRINTING_ENABLED", False)
    calls = []
    sale = _make_sale(conn)
    result = receipt_service.issue_receipt(
        conn, sale.sale_id, printer_fn=lambda p: calls.append(p)
    )
    assert result.printed is False
    assert result.warning is None
    assert calls == []  # printer never touched
    assert result.saved_path.exists()


def test_issue_receipt_unknown_sale(conn):
    with pytest.raises(ReceiptError, match="not found"):
        receipt_service.issue_receipt(conn, 9999, printer_fn=lambda _p: None)


def test_reprint_uses_same_path(conn):
    sale = _make_sale(conn)
    first = receipt_service.issue_receipt(conn, sale.sale_id, printer_fn=lambda _p: None)
    again = receipt_service.reprint_receipt(conn, sale.sale_id, printer_fn=lambda _p: None)
    assert again.saved_path == first.saved_path
    assert again.text == first.text
