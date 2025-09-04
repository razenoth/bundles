"""HTTP client for RepairShopr API with global rate limiter."""

from __future__ import annotations

import os
import random
import threading
import time
from typing import List, Dict

import requests

SUBDOMAIN = os.environ["REPAIRSHOPR_SUBDOMAIN"]
API_KEY = os.environ["REPAIRSHOPR_API_KEY"]
API_BASE = f"https://{SUBDOMAIN}.repairshopr.com/api/v1"


class TokenBucket:
    def __init__(self, capacity: int = 120, refill_per_min: int = 120) -> None:
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_per_min / 60.0
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        with self.lock:
            now = time.monotonic()
            self.tokens = min(
                self.capacity, self.tokens + (now - self.last) * self.refill_rate
            )
            self.last = now
            if self.tokens >= 1:
                self.tokens -= 1
                return
        # sleep outside the lock to avoid blocking producers
        time.sleep(0.55 + random.random() * 0.05)


bucket = TokenBucket(capacity=120, refill_per_min=120)


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
    )
    return s


def get_with_retries(url: str, params: dict | None = None) -> requests.Response:
    tries, backoff = 0, 0.5
    while True:
        bucket.acquire()
        r = session().get(url, params=params, timeout=(5, 15))
        if r.status_code < 500 and r.status_code != 429:
            r.raise_for_status()
            return r
        tries += 1
        if tries >= 3:
            r.raise_for_status()
        time.sleep(backoff + random.random() * 0.2)
        backoff = min(backoff * 2, 10.0)


def fetch_products_page(page: int, sort: str = "id ASC") -> List[Dict]:
    r = get_with_retries(f"{API_BASE}/products", params={"page": page, "sort": sort})
    data = r.json()
    return data.get("products") or data.get("data") or []


def fetch_by_barcode(barcode: str) -> Dict | None:
    r = get_with_retries(
        f"{API_BASE}/products/barcode", params={"barcode": barcode}
    )
    data = r.json()
    return data.get("product") or data


def fetch_by_sku(sku: str) -> List[Dict]:
    r = get_with_retries(f"{API_BASE}/products", params={"sku": sku, "page": 1})
    data = r.json()
    return data.get("products") or data.get("data") or []


def fetch_by_query(query: str) -> List[Dict]:
    r = get_with_retries(f"{API_BASE}/products", params={"query": query, "page": 1})
    data = r.json()
    return data.get("products") or data.get("data") or []


