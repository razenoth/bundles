# app/bundles/utils.py
from app.api.repairshopr import get_products


def search_products(q: str) -> list:
    raw = get_products(q or '')
    results = []
    for p in raw:
        results.append({
            'id': p.get('id'),
            'name': p.get('name'),
            'cost': float(p.get('price_cost', p.get('cost', 0))),
            'retail': float(p.get('price_retail', p.get('retail', 0))),
            'description': (p.get('description') or '')[:100],
            'type': 'product'
        })
    return results
