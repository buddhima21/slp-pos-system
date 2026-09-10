-- SLP POS database schema (SRS Section 5).
-- One SQLite file holds all data. Safe to run repeatedly: every statement
-- uses IF NOT EXISTS so this doubles as the migration script.

-- 5.1 products -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode       TEXT    NOT NULL UNIQUE,
    name          TEXT    NOT NULL,
    category      TEXT,
    cost_price    REAL    NOT NULL DEFAULT 0,
    sale_price    REAL    NOT NULL DEFAULT 0,
    stock_qty     INTEGER NOT NULL DEFAULT 0,
    reorder_level INTEGER NOT NULL DEFAULT 0,
    is_active     INTEGER NOT NULL DEFAULT 1   -- soft-delete flag (0/1)
);

CREATE INDEX IF NOT EXISTS idx_products_name    ON products (name);
CREATE INDEX IF NOT EXISTS idx_products_active  ON products (is_active);

-- 5.4 users --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,            -- never store plain text
    role          TEXT    NOT NULL CHECK (role IN ('cashier', 'admin')),
    is_active     INTEGER NOT NULL DEFAULT 1
);

-- 5.2 sales ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sales (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_datetime   TEXT    NOT NULL,          -- ISO 8601 timestamp
    cashier_id      INTEGER NOT NULL REFERENCES users (id),
    total_amount    REAL    NOT NULL,
    payment_method  TEXT    NOT NULL DEFAULT 'cash',
    amount_tendered REAL    NOT NULL,
    change_given    REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sales_datetime ON sales (sale_datetime);

-- 5.3 sale_items ------------------------------------------------------
CREATE TABLE IF NOT EXISTS sale_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id    INTEGER NOT NULL REFERENCES sales (id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products (id),
    quantity   INTEGER NOT NULL,
    unit_price REAL    NOT NULL,               -- price captured at time of sale
    line_total REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items (sale_id);

-- 5.5 stock_movements (optional, recommended) -----------------------------
-- Audit log for manual stock changes (restocks, corrections, write-offs),
-- kept separate from sales so stock history is fully traceable.
CREATE TABLE IF NOT EXISTS stock_movements (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id        INTEGER NOT NULL REFERENCES products (id),
    change_qty        INTEGER NOT NULL,        -- positive = added, negative = removed
    reason            TEXT    NOT NULL,
    movement_datetime TEXT    NOT NULL,
    user_id           INTEGER NOT NULL REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS idx_stock_movements_product ON stock_movements (product_id);
