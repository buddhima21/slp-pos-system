"""Phase 3 checks: product add / edit / search rules (SRS FR-1.1 - FR-1.4)."""

from __future__ import annotations

import pytest

from slp_pos.services import inventory_service
from slp_pos.services.inventory_service import InventoryError

BASE = dict(
    barcode="1111111111111",
    name="Test Cola 330ml",
    category="Beverages",
    cost_price="80",
    sale_price="120",
    stock_qty="50",
    reorder_level="10",
)


def _add(conn, **overrides):
    return inventory_service.add_product(conn, **{**BASE, **overrides})


# --- add ---------------------------------------------------------------------


def test_add_product_returns_stored_record(conn):
    product = _add(conn)
    assert product.id > 0
    assert product.name == "Test Cola 330ml"
    assert product.cost_price == 80.0
    assert product.sale_price == 120.0
    assert product.stock_qty == 50
    assert product.is_active is True


def test_add_trims_whitespace(conn):
    product = _add(conn, barcode="  222  ", name="  Spaced Name  ")
    assert product.barcode == "222"
    assert product.name == "Spaced Name"


def test_add_blank_barcode_rejected(conn):
    with pytest.raises(InventoryError, match="Barcode is required"):
        _add(conn, barcode="   ")


def test_add_blank_name_rejected(conn):
    with pytest.raises(InventoryError, match="Name is required"):
        _add(conn, name="")


def test_add_negative_price_rejected(conn):
    with pytest.raises(InventoryError, match="Sale price cannot be negative"):
        _add(conn, sale_price="-5")


def test_add_non_numeric_price_rejected(conn):
    with pytest.raises(InventoryError, match="Cost price must be a number"):
        _add(conn, cost_price="abc")


def test_add_non_integer_stock_rejected(conn):
    with pytest.raises(InventoryError, match="Stock quantity must be a whole number"):
        _add(conn, stock_qty="3.5")


def test_add_duplicate_barcode_rejected(conn):
    _add(conn)
    with pytest.raises(InventoryError, match="already used"):
        _add(conn, name="Another product")


def test_add_reports_multiple_errors_at_once(conn):
    with pytest.raises(InventoryError) as exc:
        _add(conn, barcode="", name="", sale_price="-1")
    message = str(exc.value)
    assert "Barcode is required" in message
    assert "Name is required" in message
    assert "Sale price cannot be negative" in message


def test_add_empty_category_stored_as_none(conn):
    product = _add(conn, category="   ")
    assert product.category is None


# --- update ----------------------------------------------------------------


def test_update_changes_fields(conn):
    product = _add(conn)
    updated = inventory_service.update_product(
        conn,
        product.id,
        barcode=product.barcode,
        name="Renamed Cola",
        category="Drinks",
        cost_price="85",
        sale_price="130",
        stock_qty="40",
        reorder_level="12",
    )
    assert updated.name == "Renamed Cola"
    assert updated.sale_price == 130.0
    assert updated.stock_qty == 40


def test_update_keeping_own_barcode_is_allowed(conn):
    product = _add(conn)
    updated = inventory_service.update_product(
        conn, product.id, **{**BASE, "name": "Same barcode, new name"}
    )
    assert updated.name == "Same barcode, new name"


def test_update_to_another_products_barcode_rejected(conn):
    first = _add(conn)
    second = _add(conn, barcode="9999999999999", name="Second")
    with pytest.raises(InventoryError, match="already used"):
        inventory_service.update_product(
            conn, second.id, **{**BASE, "barcode": first.barcode, "name": "Second"}
        )


def test_update_missing_product_rejected(conn):
    with pytest.raises(InventoryError, match="no longer exists"):
        inventory_service.update_product(conn, 4242, **BASE)


# --- deactivate / search -------------------------------------------------


def test_deactivate_hides_from_default_search(conn):
    product = _add(conn)
    inventory_service.deactivate_product(conn, product.id)

    assert inventory_service.search_products(conn, "Cola") == []
    with_inactive = inventory_service.search_products(
        conn, "Cola", include_inactive=True
    )
    assert len(with_inactive) == 1
    assert with_inactive[0].is_active is False


def test_reactivate_restores_visibility(conn):
    product = _add(conn)
    inventory_service.deactivate_product(conn, product.id)
    inventory_service.reactivate_product(conn, product.id)
    assert len(inventory_service.search_products(conn, "Cola")) == 1


def test_search_matches_name_and_barcode(conn):
    _add(conn, barcode="7001", name="Green Tea")
    _add(conn, barcode="7002", name="Black Coffee")

    assert len(inventory_service.search_products(conn, "tea")) == 1
    assert len(inventory_service.search_products(conn, "700")) == 2
    assert inventory_service.search_products(conn, "7002")[0].name == "Black Coffee"


def test_blank_search_returns_all_active(conn):
    _add(conn, barcode="8001", name="Item A")
    _add(conn, barcode="8002", name="Item B")
    assert len(inventory_service.search_products(conn, "")) == 2


def test_low_stock_list(conn):
    _add(conn, barcode="9001", name="Plenty", stock_qty="100", reorder_level="10")
    _add(conn, barcode="9002", name="Running Low", stock_qty="5", reorder_level="10")
    _add(conn, barcode="9003", name="Exactly At", stock_qty="10", reorder_level="10")

    low = inventory_service.get_low_stock_products(conn)
    names = {p.name for p in low}
    assert names == {"Running Low", "Exactly At"}
