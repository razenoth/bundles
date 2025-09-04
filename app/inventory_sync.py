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


def _request(sess: requests.Session, url: str, *, params: dict | None = None) -> dict:
    for attempt in range(3):
        bucket.throttle()
        start = time.monotonic()
        try:
            resp = sess.get(url, params=params)
            latency = (time.monotonic() - start) * 1000
            logging.info("RS %s %s %s %.1fms", url, params, resp.status_code, latency)
            if resp.status_code in {429} or resp.status_code >= 500:
                time.sleep(0.5 * (2**attempt) + random.random())
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(0.5 * (2**attempt) + random.random())
    raise RuntimeError("API request failed after retries")


def fetch_products_page(sess: requests.Session, page: int) -> dict:
    return _request(sess, f"{API_BASE}/products", params={"page": page})


def fetch_product_by_barcode(barcode: str) -> dict | None:
    sess = session()
    data = _request(sess, f"{API_BASE}/products/barcode", params={"barcode": barcode})
    prod = data.get("product") or data.get("data")
    if prod:
        upsert_products([prod])
    return prod


def fetch_products_by_sku(sku: str) -> list[dict]:
    sess = session()
    data = _request(sess, f"{API_BASE}/products", params={"sku": sku, "page": 1})
    prods = data.get("products") or data.get("data") or []
    if prods:
        upsert_products(prods)
    return prods


def fetch_products_query(query: str) -> list[dict]:
    sess = session()
    data = _request(sess, f"{API_BASE}/products", params={"query": query, "page": 1})
    prods = data.get("products") or data.get("data") or []
    if prods:
        upsert_products(prods)
    return prods


def full_sync() -> None:
    """Full refresh of local inventory, safe at <=120 rpm."""
    sess = session()
    page = 1
    data = fetch_products_page(sess, page)
    items = data.get("products") or data.get("data") or []
    total_pages = data.get("total_pages") or (1 if len(items) < 25 else 2)
    upsert_products(items)
    while page < total_pages:
        page += 1
        data = fetch_products_page(sess, page)
        items = data.get("products") or data.get("data") or []
        upsert_products(items)
    set_meta("inventory_last_synced_at", datetime.utcnow().isoformat() + "Z")
