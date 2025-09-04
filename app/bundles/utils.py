# app/bundles/utils.py
from app.inventory_store import search_products as _search_products
from app.repairshopr_client import (
    fetch_by_barcode,
    fetch_by_sku,
    fetch_by_query,
)


class RemoteFetch:
    """Adapter exposing network fetch helpers."""

    by_barcode = staticmethod(fetch_by_barcode)
    by_sku = staticmethod(fetch_by_sku)
    by_query = staticmethod(fetch_by_query)


def search_products(q: str, page: int = 1) -> list:
    rows = _search_products(q, page=page, remote_fetch=RemoteFetch)
    return [dict(p, type='product') for p in rows]
