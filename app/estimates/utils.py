# app/estimates/utils.py

"""Utility functions for the estimates blueprint."""

from app.api.repairshopr import (
    search_products as _search_products,
    search_customers,
)
from app.models import Bundle, EstimateItem


def search_products(q: str, page: int = 1) -> list:
    """Search RepairShopr for products matching ``q``.

    Previously this consulted a local inventory mirror and only fetched from
    the network when necessary.  To simplify the system and remove the local
    database dependency we now issue API requests directly for each search.
    The ``page`` parameter is ignored but kept for backwards compatibility.
    """

    rows = _search_products(q or "")
    return [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "description": p.get("description"),
            "unit_price": float(p.get("price_cost", 0.0)),
            "retail": float(p.get("price_retail", 0.0)),
            "type": "product",
        }
        for p in rows
    ]


def search_customers_util(q: str) -> list:
    """
    Called by /estimates/search-customer
    Wraps the RepairShopr customer search into {id,name,address,email}.
    """
    raw = search_customers(q or '') or []
    out = []
    for c in raw:
        full_name = " ".join(filter(None, [c.get('first_name'), c.get('last_name')]))
        out.append({
            'id'      : c.get('id'),
            'name'    : full_name,
            'address' : c.get('billing_address') or '',
            'email'   : c.get('email')
        })
    return out


def search_bundles(q: str) -> list:
    """
    Called by /estimates/bundles/search
    Returns saved bundles as:
      id, name, description, cost, retail, type='bundle'
    """
    term = f"%{q}%"
    bundles = Bundle.query.filter(Bundle.name.ilike(term)).all() if q else []
    results = []
    for b in bundles:
        total_cost   = sum(item.unit_price for item in b.items)
        total_retail = sum(item.retail     for item in b.items)
        results.append({
            'id'          : b.id,
            'name'        : b.name,
            'description' : (b.description or '')[:100],
            'cost'        : float(total_cost),
            'retail'      : float(total_retail),
            'type'        : 'bundle'
        })
    return results


def clone_bundle_to_items(bundle, estimate) -> list:
    """
    Used by the server‐side clone endpoint and
    legacy bundle‐POST path in add‐item.
    Produces un‐saved EstimateItem objects with:
      estimate_id, type='product', object_id, name,
      description, quantity, unit_price, retail, notes
    """
    clones = []
    for bi in bundle.items:
        clones.append(EstimateItem(
            estimate_id = (estimate.id if estimate else None),
            type        = 'product',
            object_id   = bi.object_id,
            name        = bi.name,
            description = bi.description,
            quantity    = bi.quantity,
            unit_price  = bi.unit_price,
            retail      = bi.retail,
            notes       = bi.notes or ''
        ))
    return clones
