"""
models/db.py — SQLite database helper
--------------------------------------
Provides connection management with row_factory so columns are
accessible by name (row['column_name']) in all routes and templates.
"""
import sqlite3
import os
from flask import g
import config


def get_db():
    """
    Get (or create) a database connection scoped to the current request.
    Uses Flask's application context 'g' object so each request
    gets exactly one connection that is closed at teardown.
    """
    if "db" not in g:
        g.db = sqlite3.connect(
            config.DB_PATH,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        # Enable column access by name: row['column_name']
        g.db.row_factory = sqlite3.Row
        # Enforce foreign key constraints
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    """Close the database connection at end of request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """
    Initialize the database:
    - Creates the database directory if needed.
    - Runs schema.sql to create all tables (IF NOT EXISTS — safe to re-run).
    - Seeds a default admin account if none exists.
    """
    from werkzeug.security import generate_password_hash

    # Ensure the database directory exists
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)

    # Ensure uploads directory exists
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

    # Ensure static/images exists
    os.makedirs(os.path.join(app.root_path, "static", "images"), exist_ok=True)

    # Read and execute schema
    schema_path = os.path.join(app.root_path, "database", "schema.sql")
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        with open(schema_path, "r") as f:
            conn.executescript(f.read())

        # Seed default admin account if none exists
        existing = conn.execute(
            "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()

        if not existing:
            conn.execute(
                """INSERT INTO users (name, email, phone, password, role)
                   VALUES (?, ?, ?, ?, 'admin')""",
                (
                    config.ADMIN_NAME,
                    config.ADMIN_EMAIL,
                    "0000000000",
                    generate_password_hash(config.ADMIN_PASS),
                ),
            )
            conn.commit()
            print(f"[DB] Default admin created -> {config.ADMIN_EMAIL} / {config.ADMIN_PASS}")
        else:
            print("[DB] Database initialized.")
