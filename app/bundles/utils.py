# app/bundles/utils.py
from app.inventory_store import search_products as _search_products
from app import inventory_sync


class RemoteFetch:
    """Adapter exposing network fetch helpers."""

    by_barcode = staticmethod(inventory_sync.fetch_product_by_barcode)
    by_sku = staticmethod(inventory_sync.fetch_products_by_sku)
    by_query = staticmethod(inventory_sync.fetch_products_query)


def search_products(q: str, page: int = 1) -> list:
    rows = _search_products(q, page=page, remote_fetch=RemoteFetch)
    return [dict(p, type='product') for p in rows]
