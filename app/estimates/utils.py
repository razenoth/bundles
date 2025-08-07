from app.api.repairshopr import get_products, search_customers
from app.models import EstimateItem

def search_bundles(q: str) -> list:
    from app.models import Bundle
    qstr = f"%{q}%"
    bundles = Bundle.query.filter(Bundle.title.ilike(qstr)).all()
    return [
        {
            'id'         : b.id,
            'name'       : b.title,
            'description': b.description or '',
            'cost'       : sum(i.unit_price for i in b.items),
            'retail'     : sum(i.retail_price for i in b.items),
            'type'       : 'bundle'
        }
        for b in bundles
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
