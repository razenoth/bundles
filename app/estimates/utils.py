from app.api.repairshopr import get_products, search_customers
from app.models import EstimateItem

def search_products(q):
    prods = get_products(q)
    return [
        {'id': p['id'], 'name': p['name'], 'unit_price': float(p.get('price', 0)), 'type': 'product'}
        for p in prods
    ]

def search_customers_util(q):
    """
    Wraps RepairShopr customer search and returns
    id/name/address/email for the dropdown.
    """
    raw = search_customers(q)
    out = []
    for c in raw:
        name = " ".join(filter(None, [c.get('first_name'), c.get('last_name')]))
        addr = c.get('billing_address') or ''
        out.append({
            'id': c['id'],
            'name': name,
            'address': addr,
            'email': c.get('email')
        })
    return out

def clone_bundle_to_items(bundle, estimate):
    items = []
    for bi in bundle.items:
        items.append(EstimateItem(
            estimate_id = estimate.id,
            type        = 'bundle',
            object_id   = bundle.id,
            name        = bundle.name,
            description = bi.description,
            quantity    = bi.quantity,
            unit_price  = bi.unit_price,
            retail      = bi.unit_price,  # or apply your markup
            notes       = ''
        ))
    return items
