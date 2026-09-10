"""Insert a small set of sample products for development and testing.

Run:  python -m slp_pos.db.seed
Not used in production — the real catalog is loaded on the store PC (SRS 10.1).
"""

from __future__ import annotations

from pathlib import Path

from slp_pos import config
from slp_pos.db.connection import get_connection
from slp_pos.db.migrate import migrate

# barcode, name, category, cost_price, sale_price, stock_qty, reorder_level
SAMPLE_PRODUCTS = [
    ("4001234567890", "White Bread 450g", "Bakery", 90.00, 130.00, 40, 10),
    ("4002345678901", "Fresh Milk 1L", "Dairy", 210.00, 280.00, 25, 8),
    ("4003456789012", "Large Eggs (10pk)", "Dairy", 320.00, 420.00, 18, 6),
    ("4004567890123", "Basmati Rice 5kg", "Grocery", 1650.00, 1990.00, 12, 4),
    ("4005678901234", "Sunflower Oil 1L", "Grocery", 640.00, 780.00, 20, 6),
    ("4006789012345", "Sugar 1kg", "Grocery", 240.00, 290.00, 30, 10),
    ("4007890123456", "Tea Leaves 200g", "Beverages", 380.00, 470.00, 22, 8),
    ("4008901234567", "Instant Coffee 100g", "Beverages", 690.00, 850.00, 15, 5),
    ("4009012345678", "Biscuits Assorted", "Snacks", 120.00, 170.00, 50, 15),
    ("4010123456789", "Potato Chips 100g", "Snacks", 150.00, 210.00, 35, 12),
    ("4011234567890", "Dish Wash Liquid 500ml", "Household", 260.00, 340.00, 16, 5),
    ("4012345678901", "Toothpaste 120g", "Personal Care", 210.00, 290.00, 24, 8),
    ("4013456789012", "Bath Soap 100g", "Personal Care", 95.00, 140.00, 40, 12),
    ("4014567890123", "Mineral Water 1.5L", "Beverages", 60.00, 100.00, 60, 20),
    ("4015678901234", "Chocolate Bar 80g", "Snacks", 180.00, 250.00, 28, 10),
]


def seed(db_path: str | Path | None = None) -> int:
    """Add sample products that are not already present. Returns count inserted."""
    migrate(db_path)
    conn = get_connection(db_path)
    inserted = 0
    try:
        for barcode, name, category, cost, price, qty, reorder in SAMPLE_PRODUCTS:
            exists = conn.execute(
                "SELECT 1 FROM products WHERE barcode = ?", (barcode,)
            ).fetchone()
            if exists:
                continue
            conn.execute(
                "INSERT INTO products "
                "(barcode, name, category, cost_price, sale_price, stock_qty, reorder_level) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (barcode, name, category, cost, price, qty, reorder),
            )
            inserted += 1
        conn.commit()
    finally:
        conn.close()
    return inserted


if __name__ == "__main__":
    n = seed()
    print(f"Seeded {n} new sample product(s) into {config.DB_PATH}")
