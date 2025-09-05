import os
import requests
from requests.exceptions import HTTPError, RequestException

API_URL = os.getenv('REPAIRSHOPR_API_URL') or \
          f"https://{os.getenv('REPAIRSHOPR_SUBDOMAIN')}.repairshopr.com/api/v1"
API_KEY = os.getenv('REPAIRSHOPR_API_KEY')

def get_products(query):
    """Returns a list of product dicts from RepairShopr matching ``query``.

    RepairShopr's product endpoint can search by different fields (name,
    description, SKU, etc.).  To make our search more forgiving we attempt all
    of these lookups and merge the unique results.  If one lookup fails we log
    the error and continue trying the others so a partial failure doesn't
    prevent returning results.
    """
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Accept': 'application/json'
    }

    results = []
    seen_ids = set()

    # Try multiple search parameter variations.  The RepairShopr API supports
    # searching by different fields depending on the parameter name.  To keep
    # the search fast we limit lookups to name and SKU only.
    param_sets = [
        {'name': query},  # explicit name search
        {'sku': query},   # SKU lookup
    ]

    for params in param_sets:
        try:
            resp = requests.get(f"{API_URL}/products", params=params, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
            products = payload.get('products', payload) or []
            for p in products:
                pid = p.get('id')
                if pid not in seen_ids:
                    results.append(p)
                    seen_ids.add(pid)
        except HTTPError as e:
            if e.response.status_code == 401:
                print("🚨 401 Unauthorized from RepairShopr. Check your API key.")
            else:
                print(f"⚠️ RepairShopr API error ({e.response.status_code}): {e}")
        except RequestException as e:
            print(f"⚠️ RepairShopr network error: {e}")

    return results

def search_products(query):
    """
    Returns a list of dicts with:
      id, name, description (<=100 chars), price_cost, price_retail, quantity
    """
    raw = get_products(query) or []
    out = []
    for p in raw:
        desc = (p.get('description') or '').strip()
        if len(desc) > 100:
            desc = desc[:100] + '…'
        out.append({
            'id':            p['id'],
            'name':          p.get('name'),
            'description':   desc, 
            'price_cost':    float(p.get('price_cost', 0)),    # cost :contentReference[oaicite:1]{index=1}
            'price_retail':  float(p.get('price_retail', 0)),  # retail :contentReference[oaicite:2]{index=2}
            'quantity':      float(p.get('quantity', 0))
        })
    return out

def search_customers(query):
    """Search customers by name or email."""
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Accept': 'application/json'
    }
    try:
        resp = requests.get(f"{API_URL}/customers", params={'search': query}, headers=headers)
        resp.raise_for_status()
        payload = resp.json()
        return payload.get('customers', payload)
    except HTTPError as e:
        print(f"⚠️ RepairShopr API error ({e.response.status_code}): {e}")
    except RequestException as e:
        print(f"⚠️ RepairShopr network error: {e}")
    return []

def get_customer(customer_id):
    """Fetch a single customer's full details."""
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Accept': 'application/json'
    }
    try:
        resp = requests.get(f"{API_URL}/customers/{customer_id}", headers=headers)
        resp.raise_for_status()
        payload = resp.json()
        return payload.get('customer')
    except HTTPError as e:
        print(f"⚠️ RepairShopr API error ({e.response.status_code}): {e}")
    except RequestException as e:
        print(f"⚠️ RepairShopr network error: {e}")
    return None
