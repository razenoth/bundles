"""Compatibility layer for RepairShopr API access using shared rate limiter."""
from __future__ import annotations

from typing import Dict, List

from app.integrations.repairshopr_export import RepairShoprClient

client = RepairShoprClient()


def fetch_products_page(page: int, sort: str = "id ASC") -> List[Dict]:
    data = client.get("/products", params={"page": page, "sort": sort})
    return data.get("products") or data.get("data") or []


def fetch_by_barcode(barcode: str) -> Dict | None:
    data = client.get("/products/barcode", params={"barcode": barcode})
    return data.get("product") or data


def fetch_by_sku(sku: str) -> List[Dict]:
    data = client.get("/products", params={"sku": sku, "page": 1})
    return data.get("products") or data.get("data") or []


def fetch_by_query(query: str) -> List[Dict]:
    data = client.get("/products", params={"query": query, "page": 1})
    return data.get("products") or data.get("data") or []
