# app/bundles/utils.py
"""Helpers for bundle-related product search."""

from app.api.repairshopr import search_products as _search_products


def search_products(q: str, page: int = 1) -> list:
    """Search for products via the RepairShopr API.

    The previous implementation queried a local inventory mirror and only
    contacted the API on cache misses.  This reverts to the simpler behaviour
    of hitting the API directly for every search.  The ``page`` argument is
    accepted for compatibility but currently unused as the API endpoint does
    not support pagination for these lookups.
    """

    rows = _search_products(q or "")
    return [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "description": p.get("description"),
            "cost": float(p.get("price_cost", 0.0)),
            "retail": float(p.get("price_retail", 0.0)),
            "type": "product",
        }
        for p in rows
    ]
