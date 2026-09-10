"""Phase 4 checks: cart maths and sale completion (SRS FR-2.1 - FR-2.5, 9.1)."""

from __future__ import annotations

import pytest

from slp_pos.data import products_repo, sales_repo
from slp_pos.services import checkout_service
from slp_pos.services.checkout_service import Cart, CheckoutError

CASHIER_ID = 1  # the seeded admin


def _product(conn, *, barcode, name, price, stock):
    pid = products_repo.insert(
        conn,
        barcode=barcode,
        name=name,
        category=None,
        cost_price=price / 2,
        sale_price=price,
        stock_qty=stock,
        reorder_level=0,
    )
    return products_repo.get_by_id(conn, pid)


# --- cart maths ------------------------------------------------------------


def test_cart_totals_and_merge(conn):
    cola = _product(conn, barcode="1", name="Cola", price=120.0, stock=10)
    chips = _product(conn, barcode="2", name="Chips", price=210.0, stock=10)

    cart = Cart()
    cart.add_product(cola, 2)
    cart.add_product(chips, 1)
    cart.add_product(cola, 1)  # merges -> qty 3

    assert cart.item_count == 4
    assert cart.get(cola.id).quantity == 3
    assert cart.subtotal == pytest.approx(120 * 3 + 210)
    assert cart.total == cart.subtotal


def test_set_quantity_zero_removes_line(conn):
    cola = _product(conn, barcode="1", name="Cola", price=100.0, stock=10)
    cart = Cart()
    cart.add_product(cola, 3)
    cart.set_quantity(cola.id, 0)
    assert cart.is_empty


def test_add_to_cart_rejects_inactive_product(conn):
    cola = _product(conn, barcode="1", name="Cola", price=100.0, stock=10)
    products_repo.set_active(conn, cola.id, False)
    cart = Cart()
    with pytest.raises(CheckoutError, match="not available"):
        checkout_service.add_to_cart(conn, cart, cola.id)


def test_add_by_barcode_unknown(conn):
    cart = Cart()
    with pytest.raises(CheckoutError, match="No product found"):
        checkout_service.add_by_barcode(conn, cart, "does-not-exist")


# --- change / tender -----------------------------------------------------


def test_change_due_exact_and_over(conn):
    assert checkout_service.change_due(100.0, "100") == 0.0
    assert checkout_service.change_due(100.0, "150") == 50.0


def test_change_due_insufficient_rejected(conn):
    with pytest.raises(CheckoutError, match="less than the total"):
        checkout_service.change_due(100.0, "80")


def test_change_due_non_numeric_rejected(conn):
    with pytest.raises((CheckoutError, ValueError)):
        checkout_service.change_due(100.0, "abc")


# --- complete_sale: SRS 9.1 scenarios -----------------------------------


def test_single_item_exact_cash(conn):
    cola = _product(conn, barcode="1", name="Cola", price=120.0, stock=10)
    cart = Cart()
    cart.add_product(cola, 1)

    sale = checkout_service.complete_sale(
        conn, cart, cashier_id=CASHIER_ID, amount_tendered="120"
    )

    assert sale.total == 120.0
    assert sale.change_given == 0.0
    assert cart.is_empty  # cart cleared after completion

    stored = sales_repo.get_sale(conn, sale.sale_id)
    assert stored.total_amount == 120.0
    items = sales_repo.get_sale_items(conn, sale.sale_id)
    assert len(items) == 1 and items[0].quantity == 1
    assert products_repo.get_by_id(conn, cola.id).stock_qty == 9  # FR-1.5


def test_multiple_items_mixed_quantities(conn):
    a = _product(conn, barcode="1", name="A", price=100.0, stock=5)
    b = _product(conn, barcode="2", name="B", price=250.0, stock=5)
    cart = Cart()
    cart.add_product(a, 3)
    cart.add_product(b, 2)

    sale = checkout_service.complete_sale(
        conn, cart, cashier_id=CASHIER_ID, amount_tendered="1000"
    )
    assert sale.total == pytest.approx(800.0)
    assert sale.change_given == pytest.approx(200.0)
    assert products_repo.get_by_id(conn, a.id).stock_qty == 2
    assert products_repo.get_by_id(conn, b.id).stock_qty == 3


def test_cannot_complete_empty_sale(conn):
    with pytest.raises(CheckoutError, match="at least one item"):
        checkout_service.complete_sale(
            conn, Cart(), cashier_id=CASHIER_ID, amount_tendered="0"
        )


def test_tendered_less_than_total_rejected(conn):
    cola = _product(conn, barcode="1", name="Cola", price=120.0, stock=10)
    cart = Cart()
    cart.add_product(cola, 1)
    with pytest.raises(CheckoutError, match="less than the total"):
        checkout_service.complete_sale(
            conn, cart, cashier_id=CASHIER_ID, amount_tendered="100"
        )


def test_overselling_blocked(conn):
    cola = _product(conn, barcode="1", name="Cola", price=120.0, stock=2)
    cart = Cart()
    cart.add_product(cola, 5)
    with pytest.raises(CheckoutError, match="Not enough stock"):
        checkout_service.complete_sale(
            conn, cart, cashier_id=CASHIER_ID, amount_tendered="1000"
        )
    # nothing recorded, stock untouched
    assert sales_repo.count_sales(conn) == 0
    assert products_repo.get_by_id(conn, cola.id).stock_qty == 2


def test_failed_sale_records_nothing(conn):
    """A failure part-way must leave no sale row and no stock change (FR-2.5)."""
    a = _product(conn, barcode="1", name="A", price=100.0, stock=10)
    b = _product(conn, barcode="2", name="B", price=100.0, stock=1)
    cart = Cart()
    cart.add_product(a, 1)
    cart.add_product(b, 5)  # short

    with pytest.raises(CheckoutError):
        checkout_service.complete_sale(
            conn, cart, cashier_id=CASHIER_ID, amount_tendered="1000"
        )

    assert sales_repo.count_sales(conn) == 0
    assert products_repo.get_by_id(conn, a.id).stock_qty == 10
    assert products_repo.get_by_id(conn, b.id).stock_qty == 1


def test_unit_price_captured_at_sale_time(conn):
    cola = _product(conn, barcode="1", name="Cola", price=120.0, stock=10)
    cart = Cart()
    cart.add_product(cola, 1)
    sale = checkout_service.complete_sale(
        conn, cart, cashier_id=CASHIER_ID, amount_tendered="120"
    )
    # later price change must not affect the recorded sale
    products_repo.update(
        conn,
        cola.id,
        barcode="1",
        name="Cola",
        category=None,
        cost_price=60.0,
        sale_price=999.0,
        stock_qty=9,
        reorder_level=0,
    )
    items = sales_repo.get_sale_items(conn, sale.sale_id)
    assert items[0].unit_price == 120.0
