# app/inventory_store.py
"""SQLite-backed inventory mirror with FTS5 support."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from flask import current_app

DB_FILENAME = "inventory.db"


def _db_path() -> str:
    """Return the absolute path to the inventory database file."""
    return os.path.join(current_app.instance_path, DB_FILENAME)


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply performance related pragmas on the connection."""
    pragma_statements = [
        "PRAGMA journal_mode=WAL",  # allows concurrent reads
        "PRAGMA synchronous=NORMAL",
        "PRAGMA temp_store=MEMORY",
        "PRAGMA cache_size=-20000",
    ]
    for stmt in pragma_statements:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            # Ignore failures on read-only connections.
            pass


def init_db() -> None:
    """Initialise database and schema if not already present."""
    os.makedirs(current_app.instance_path, exist_ok=True)
    conn = sqlite3.connect(_db_path())
    _apply_pragmas(conn)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT,
            sku TEXT,
            upc_code TEXT,
            category_id INTEGER,
            price_cents INTEGER,
            active INTEGER,
            updated_at TEXT,
            raw_json TEXT
        )
        """
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_products_upc ON products(upc_code)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_products_active ON products(active)")
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    c.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
            name, sku
        )
        """
    )
    # Triggers to keep FTS table in sync with products
    c.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS products_ai AFTER INSERT ON products BEGIN
            INSERT INTO products_fts(rowid, name, sku) VALUES (new.id, new.name, new.sku);
        END;
        CREATE TRIGGER IF NOT EXISTS products_au AFTER UPDATE ON products BEGIN
            INSERT INTO products_fts(products_fts, rowid, name, sku)
            VALUES('delete', old.id, old.name, old.sku);
            INSERT INTO products_fts(rowid, name, sku) VALUES (new.id, new.name, new.sku);
        END;
        CREATE TRIGGER IF NOT EXISTS products_ad AFTER DELETE ON products BEGIN
            INSERT INTO products_fts(products_fts, rowid, name, sku)
            VALUES('delete', old.id, old.name, old.sku);
        END;
        """
    )
    conn.commit()
    conn.close()


@contextmanager
def ro_conn():
    """Yield a read-only SQLite connection."""
    uri = f"file:{_db_path()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    try:
        yield conn
    finally:
        conn.close()


def _rw_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    return conn


def upsert_products(rows: list[dict]) -> None:
    """Insert or update product rows."""
    if not rows:
        return
    conn = _rw_conn()
    c = conn.cursor()
    for p in rows:
        c.execute(
            """
            INSERT INTO products
                (id, name, sku, upc_code, category_id, price_cents, active, updated_at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                sku=excluded.sku,
                upc_code=excluded.upc_code,
                category_id=excluded.category_id,
                price_cents=excluded.price_cents,
                active=excluded.active,
                updated_at=excluded.updated_at,
                raw_json=excluded.raw_json
            """,
            (
                p.get("id"),
                p.get("name"),
                p.get("sku"),
                p.get("upc_code"),
                p.get("category_id"),
                int(float(p.get("price_retail", p.get("price", 0))) * 100),
                int(bool(p.get("active", True))),
                p.get("updated_at") or datetime.utcnow().isoformat() + "Z",
                json.dumps(p),
            ),
        )
    conn.commit()
    conn.close()


def set_meta(key: str, value: str) -> None:
    conn = _rw_conn()
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_meta(key: str, default: str | None = None) -> str | None:
    with ro_conn() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        if row:
            return row["value"]
    return default


def list_products(limit: int = 50) -> list[dict]:
    """Return a list of products stored in the mirror database.

    The result includes a ``quantity`` field extracted from the raw JSON
    payload so admins can verify stock levels after a sync.
    """
    with ro_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, sku, raw_json FROM products ORDER BY id LIMIT ?",
            (limit,),
        ).fetchall()
    products: list[dict] = []
    for r in rows:
        raw = json.loads(r["raw_json"] or "{}")
        qty = (
            raw.get("quantity_on_hand")
            or raw.get("quantity")
            or raw.get("qty")
            or 0
        )
        products.append(
            {"id": r["id"], "name": r["name"], "sku": r["sku"], "quantity": qty}
        )
    return products


def _row_to_product(row: sqlite3.Row) -> dict:
    raw = json.loads(row["raw_json"] or "{}")
    desc = (raw.get("description") or "")[:100]
    return {
        "id": row["id"],
        "name": row["name"],
        "description": desc,
        "cost": float(raw.get("price_cost", 0)),
        "retail": float(raw.get("price_retail", row["price_cents"] / 100 if row["price_cents"] else 0)),
    }


def _search_local_by(field: str, value: str) -> list[dict]:
    query = f"SELECT * FROM products WHERE {field} = ? AND active = 1"
    with ro_conn() as conn:
        rows = conn.execute(query, (value,)).fetchall()
    return [_row_to_product(r) for r in rows]


def _fts_search(q: str, limit: int, offset: int) -> list[dict]:
    sql = (
        "SELECT p.* FROM products p JOIN products_fts f ON p.id = f.rowid "
        "WHERE products_fts MATCH ? AND active = 1 LIMIT ? OFFSET ?"
    )
    with ro_conn() as conn:
        rows = conn.execute(sql, (q, limit, offset)).fetchall()
    return [_row_to_product(r) for r in rows]


BARCODE_RE = re.compile(r"^\d{8,14}$")
SKU_RE = re.compile(r"^(?=.*[\d_-])[\w-]+$")


def search_products(q: str, page: int = 1, remote_fetch=None) -> list[dict]:
    """Local-first product search with optional remote fallback.

    ``remote_fetch`` is an object providing ``by_barcode``, ``by_sku`` and
    ``by_query`` callables.  This indirection allows tests to inject fakes and
    keeps this module free of RepairShopr-specific code.
    """
    q = (q or "").strip()
    if not q:
        return []

    limit = 25
    offset = (page - 1) * limit

    if BARCODE_RE.fullmatch(q):
        rows = _search_local_by("upc_code", q)
        if rows:
            return rows
        if remote_fetch:
            fetched = remote_fetch.by_barcode(q)
            if fetched:
                upsert_products([fetched])
                return [_row_to_product_from_remote(fetched)]
        return []

    if SKU_RE.fullmatch(q):
        rows = _search_local_by("sku", q)
        if rows:
            return rows
        if remote_fetch:
            prods = remote_fetch.by_sku(q) or []
            if prods:
                upsert_products(prods)
                return [_row_to_product_from_remote(p) for p in prods]
        return []

    rows = _fts_search(q, limit, offset)
    if rows:
        return rows
    if remote_fetch and page == 1:
        prods = remote_fetch.by_query(q) or []
        if prods:
            upsert_products(prods)
            return [_row_to_product_from_remote(p) for p in prods]
    return []


def _row_to_product_from_remote(p: dict) -> dict:
    desc = (p.get("description") or "")[:100]
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "description": desc,
        "cost": float(p.get("price_cost", 0)),
        "retail": float(p.get("price_retail", p.get("price", 0))),
    }
