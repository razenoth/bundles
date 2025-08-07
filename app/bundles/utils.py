# app/bundles/utils.py
from app.api.repairshopr import get_products


def search_products(q: str) -> list:
    raw = get_products(q or '') or []
    return [
        {
            'id'         : p['id'],
            'name'       : p.get('name'),
            'description': (p.get('description') or '')[:100],
            'cost'       : float(p.get('price_cost', 0)),
            'retail'     : float(p.get('price_retail', 0)),
            'type'       : 'product'
        }
        for p in raw
    ]
