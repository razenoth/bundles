# app/inventory_sync.py
"""Synchronisation helpers for the inventory mirror."""

from __future__ import annotations

import logging
import os
import random
import threading
import time
from datetime import datetime

import requests

from .inventory_store import upsert_products, set_meta

API_BASE = f"https://{os.environ.get('REPAIRSHOPR_SUBDOMAIN')}.repairshopr.com/api/v1"
API_KEY = os.environ.get('REPAIRSHOPR_API_KEY')


class TokenBucket:
    """Simple token bucket rate limiter."""

    def __init__(self, capacity: int = 120, refill_per_min: int = 120) -> None:
        self.capacity = capacity
        self.tokens = capacity
        self.refill = refill_per_min / 60.0
        self.t = time.monotonic()
        self.lock = threading.Lock()

    def throttle(self) -> None:
        with self.lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.t) * self.refill)
            self.t = now
            if self.tokens >= 1:
                self.tokens -= 1
                return
            wait = (1 - self.tokens) / self.refill
        time.sleep(wait)


bucket = TokenBucket(capacity=120, refill_per_min=120)


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
    })
    s.timeout = (3, 10)
    return s


def _request(
    sess: requests.Session, url: str, *, params: dict | None = None
) -> tuple[dict, int, float]:
    """Perform a GET request with retries and return JSON, status and latency."""
    for attempt in range(3):
        bucket.throttle()
        start = time.monotonic()
        try:
            resp = sess.get(url, params=params)
            latency = (time.monotonic() - start) * 1000
            logging.info("RS %s %s %s %.1fms", url, params, resp.status_code, latency)
            if resp.status_code in {429} or resp.status_code >= 500:
                # Retryable errors
                time.sleep(0.5 * (2**attempt) + random.random())
                continue
            resp.raise_for_status()
            return resp.json(), resp.status_code, latency
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(0.5 * (2**attempt) + random.random())
    raise RuntimeError("API request failed after retries")


def fetch_products_page(
    sess: requests.Session, page: int
) -> tuple[list[dict], int, float]:
    data, status, latency = _request(
        sess, f"{API_BASE}/products", params={"page": page}
    )
    items = data.get("products") or data.get("data") or []
    return items, status, latency


def fetch_product_by_barcode(barcode: str) -> dict | None:
    sess = session()
    data, _, _ = _request(
        sess, f"{API_BASE}/products/barcode", params={"barcode": barcode}
    )
    prod = data.get("product") or data.get("data")
    if prod:
        upsert_products([prod])
    return prod


def fetch_products_by_sku(sku: str) -> list[dict]:
    sess = session()
    data, _, _ = _request(
        sess, f"{API_BASE}/products", params={"sku": sku, "page": 1}
    )
    prods = data.get("products") or data.get("data") or []
    if prods:
        upsert_products(prods)
    return prods


def fetch_products_query(query: str) -> list[dict]:
    sess = session()
    data, _, _ = _request(
        sess, f"{API_BASE}/products", params={"query": query, "page": 1}
    )
    prods = data.get("products") or data.get("data") or []
    if prods:
        upsert_products(prods)
    return prods


PAGE_SIZE = 25


def utcnow_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def full_sync() -> None:
    """Full refresh of local inventory, safe at <=120 rpm."""
    sess = session()
    page = 1
    total = 0
    pages_fetched = 0
    requests_made = 0
    try:
        while True:
            set_meta("inventory_sync_status", "fetching")
            items, status, latency = fetch_products_page(sess, page)
            logging.info(
                "sync page=%s items=%s total=%s status=%s %.1fms",
                page,
                len(items),
                total + len(items),
                status,
                latency,
            )
            if not items:
                break
            upsert_products(items)
            total += len(items)
            pages_fetched = page
            requests_made += 1
            if len(items) < PAGE_SIZE:
                break
            page += 1
            if requests_made % 120 == 0:
                set_meta("inventory_sync_status", "waiting")
                time.sleep(60)
        set_meta("inventory_last_synced_at", utcnow_iso())
        set_meta("inventory_last_synced_count", str(total))
        set_meta("inventory_last_error", "")
        set_meta("inventory_sync_status", "completed")
        logging.info(
            "sync completed pages=%s total_items=%s", pages_fetched, total
        )
    except Exception as e:  # pragma: no cover - exercised in tests via error handling
        set_meta(
            "inventory_last_error",
            f"{utcnow_iso()} {type(e).__name__}: {e}",
        )
        logging.exception("inventory sync failed: %s", e)
        raise
    finally:
        set_meta("inventory_sync_running", "0")
        set_meta("inventory_sync_status", "completed")
