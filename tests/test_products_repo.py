"""Data-access checks for products_repo (SQL layer)."""

from __future__ import annotations

from slp_pos.data import products_repo


def _insert(conn, **overrides):
    fields = dict(
        barcode="5551",
        name="Repo Widget",
        category="Misc",
        cost_price=10.0,
        sale_price=15.0,
        stock_qty=7,
        reorder_level=3,
    )
    fields.update(overrides)
    return products_repo.insert(conn, **fields)


def test_insert_and_get_by_id(conn):
    pid = _insert(conn)
    product = products_repo.get_by_id(conn, pid)
    assert product is not None
    assert product.barcode == "5551"
    assert product.is_active is True


def test_get_by_barcode_strips_input(conn):
    _insert(conn, barcode="5552")
    assert products_repo.get_by_barcode(conn, "  5552 ") is not None


def test_list_all_excludes_inactive_by_default(conn):
    active = _insert(conn, barcode="6001", name="Active")
    hidden = _insert(conn, barcode="6002", name="Hidden")
    products_repo.set_active(conn, hidden, False)

    names = {p.name for p in products_repo.list_all(conn)}
    assert names == {"Active"}
    assert len(products_repo.list_all(conn, include_inactive=True)) == 2


def test_adjust_stock(conn):
    pid = _insert(conn, stock_qty=10)
    products_repo.adjust_stock(conn, pid, -4)
    assert products_repo.get_by_id(conn, pid).stock_qty == 6


def test_is_low_stock_flag(conn):
    pid = _insert(conn, stock_qty=2, reorder_level=5)
    assert products_repo.get_by_id(conn, pid).is_low_stock is True
