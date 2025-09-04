"""Local SQLite inventory mirror and sync state store."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable, Dict, Any, List

from flask import current_app

DB_FILENAME = "inventory.db"

# Fields participating in checksum calculation
CHECKSUM_FIELDS = (
    "name",
    "sku",
    "upc_code",
    "category_id",
    "price_cents",
    "disabled",
)


def utcnow_iso() -> str:
    """Return current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def product_checksum(p: Dict[str, Any]) -> str:
    """Compute deterministic checksum for stable product fields."""
    payload = {k: p.get(k) for k in CHECKSUM_FIELDS}
    s = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _db_path() -> str:
    return os.path.join(current_app.instance_path, DB_FILENAME)


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    pragma_statements = [
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA temp_store=MEMORY",
        "PRAGMA cache_size=-20000",
    ]
    for stmt in pragma_statements:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
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
            disabled INTEGER,
            last_seen_at TEXT,
            checksum TEXT,
            raw_json TEXT
        )
        """
    )
    # Existing installations may lack newer columns; ensure they are present
    cols = [r[1] for r in c.execute("PRAGMA table_info(products)")]
    if "last_seen_at" not in cols:
        c.execute("ALTER TABLE products ADD COLUMN last_seen_at TEXT")
    if "disabled" not in cols:
        # Add column with default 0 so existing rows are treated as enabled
        c.execute("ALTER TABLE products ADD COLUMN disabled INTEGER DEFAULT 0")
    if "checksum" not in cols:
        c.execute("ALTER TABLE products ADD COLUMN checksum TEXT")

    c.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_products_upc ON products(upc_code)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_products_disabled ON products(disabled)")
    # sync_state table stores a single row with sync metadata
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_full_sync_at TEXT,
            last_quick_check_at TEXT,
            max_product_id_seen INTEGER,
            next_audit_page INTEGER,
            inventory_sync_running INTEGER DEFAULT 0,
            last_error TEXT,
            last_job_result TEXT
        )
        """
    )
    conn.commit()
    conn.close()


@contextmanager
def ro_conn():
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


def _normalize_product(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "sku": p.get("sku"),
        "upc_code": p.get("upc_code"),
        "category_id": p.get("category_id"),
        "price_cents": int(
            float(p.get("price_retail", p.get("price", 0) or 0)) * 100
        ),
        "disabled": int(not p.get("active", True) or p.get("disabled", False)),
    }


def upsert_products(products: Iterable[Dict[str, Any]]) -> None:
    products = list(products)
    if not products:
        return
    conn = _rw_conn()
    c = conn.cursor()
    now = utcnow_iso()
    for p in products:
        norm = _normalize_product(p)
        checksum = product_checksum(norm)
        c.execute(
            """
            INSERT INTO products
                (id, name, sku, upc_code, category_id, price_cents, disabled,
                 last_seen_at, checksum, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                sku=excluded.sku,
                upc_code=excluded.upc_code,
                category_id=excluded.category_id,
                price_cents=excluded.price_cents,
                disabled=excluded.disabled,
                last_seen_at=excluded.last_seen_at,
                checksum=excluded.checksum,
                raw_json=excluded.raw_json
            """,
            (
                norm["id"],
                norm["name"],
                norm["sku"],
                norm["upc_code"],
                norm["category_id"],
                norm["price_cents"],
                norm["disabled"],
                now,
                checksum,
                json.dumps(p),
            ),
        )
    conn.commit()
    conn.close()


def get_sync_state() -> Dict[str, Any]:
    with ro_conn() as conn:
        row = conn.execute("SELECT * FROM sync_state WHERE id = 1").fetchone()
    return dict(row) if row else {}


def set_sync_state(updates: Dict[str, Any]) -> None:
    if not updates:
        return
    conn = _rw_conn()
    conn.execute("INSERT OR IGNORE INTO sync_state(id) VALUES(1)")
    cols = ", ".join(f"{k} = ?" for k in updates.keys())
    params = list(updates.values())
    conn.execute(f"UPDATE sync_state SET {cols} WHERE id = 1", params)
    conn.commit()
    conn.close()


def fetch_known_max_id() -> int:
    with ro_conn() as conn:
        row = conn.execute(
            "SELECT max_product_id_seen FROM sync_state WHERE id = 1"
        ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def compute_local_checksum(p: Dict[str, Any]) -> str | None:
    """Return existing checksum while storing remote checksum on ``p``."""
    norm = _normalize_product(p)
    remote_cs = product_checksum(norm)
    p["_local_checksum"] = remote_cs
    with ro_conn() as conn:
        row = conn.execute(
            "SELECT checksum FROM products WHERE id = ?", (p.get("id"),)
        ).fetchone()
    return row["checksum"] if row else None


# ---- Search helpers -----------------------------------------------------

def _row_to_product(row: sqlite3.Row) -> Dict[str, Any]:
    raw = json.loads(row["raw_json"] or "{}")
    desc = (raw.get("description") or "")[:100]
    return {
        "id": row["id"],
        "name": row["name"],
        "description": desc,
        "cost": float(raw.get("price_cost", 0)),
        "retail": float(
            raw.get("price_retail", row["price_cents"] / 100 if row["price_cents"] else 0)
        ),
    }


def _search_local_by(field: str, value: str) -> List[Dict[str, Any]]:
    query = f"SELECT * FROM products WHERE {field} = ? AND disabled = 0"
    with ro_conn() as conn:
        rows = conn.execute(query, (value,)).fetchall()
    return [_row_to_product(r) for r in rows]


def _fts_search(q: str, limit: int, offset: int) -> List[Dict[str, Any]]:
    term = f"%{q}%"
    sql = "SELECT * FROM products WHERE name LIKE ? AND disabled = 0 LIMIT ? OFFSET ?"
    with ro_conn() as conn:
        rows = conn.execute(sql, (term, limit, offset)).fetchall()
    return [_row_to_product(r) for r in rows]


BARCODE_RE = re.compile(r"^\d{8,14}$")
SKU_RE = re.compile(r"^(?=.*[\d_-])[\w-]+$")


def search_products(q: str, page: int = 1, remote_fetch=None) -> List[Dict[str, Any]]:
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


def _row_to_product_from_remote(p: Dict[str, Any]) -> Dict[str, Any]:
    desc = (p.get("description") or "")[:100]
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "description": desc,
        "cost": float(p.get("price_cost", 0)),
        "retail": float(p.get("price_retail", p.get("price", 0))),
    }


