from app.api.repairshopr import get_products
from app.models import EstimateItem

def search_products(q):
    prods = get_products(q)
    return [
        {'id': p['id'], 'name': p['name'], 'unit_price': float(p.get('price',0)), 'type':'product'}
        for p in prods
    ]

def clone_bundle_to_items(bundle, estimate):
    items = []
    for bi in bundle.items:
        items.append(EstimateItem(
            estimate_id=estimate.id,
            description=bi.description,
            quantity=bi.quantity,
            unit_price=bi.unit_price
        ))
    return items
