-- schema.sql — Database schema for AI Food Quality Analysis System
-- All tables use INTEGER PRIMARY KEY (auto-increment in SQLite)

-- -------------------------------------------------------
-- Users table: stores both customers and admins
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    email       TEXT    NOT NULL UNIQUE,
    phone       TEXT,
    password    TEXT    NOT NULL,
    role        TEXT    NOT NULL DEFAULT 'customer', -- 'customer' | 'admin'
    profile_pic TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- -------------------------------------------------------
-- Products table: uploaded food packages
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    product_name  TEXT    NOT NULL,
    brand         TEXT    NOT NULL,
    category      TEXT    NOT NULL,
    purchase_date TEXT    NOT NULL,
    image         TEXT    NOT NULL,   -- filename in static/uploads/
    bill_image    TEXT,               -- optional bill image filename
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- -------------------------------------------------------
-- Scans table: AI analysis results per product
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS scans (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id           INTEGER NOT NULL,
    expiry_date          TEXT,
    manufacturing_date   TEXT,
    package_condition    TEXT,
    damage_percentage    TEXT,
    barcode              TEXT,
    quality_score        TEXT,
    status               TEXT,   -- 'Safe' | 'Warning' | 'Unsafe'
    scan_date            TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

-- -------------------------------------------------------
-- Complaints table: complaints raised against scans
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS complaints (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id TEXT    NOT NULL UNIQUE,  -- auto-generated e.g. CMP-20260001
    scan_id      INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    description  TEXT    NOT NULL,
    image        TEXT,    -- complaint image filename
    bill_image   TEXT,    -- purchase bill filename
    status       TEXT    NOT NULL DEFAULT 'Pending', -- 'Pending'|'Approved'|'Rejected'|'Resolved'
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (scan_id)  REFERENCES scans(id)  ON DELETE CASCADE,
    FOREIGN KEY (user_id)  REFERENCES users(id)  ON DELETE CASCADE
);
