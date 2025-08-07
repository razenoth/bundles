import os
import requests
from requests.exceptions import HTTPError, RequestException

API_URL = os.getenv('REPAIRSHOPR_API_URL') or \
          f"https://{os.getenv('REPAIRSHOPR_SUBDOMAIN')}.repairshopr.com/api/v1"
API_KEY = os.getenv('REPAIRSHOPR_API_KEY')

def get_products(query):
    """Returns a list of product dicts from RepairShopr matching `query`."""
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Accept': 'application/json'
    }
    try:
        resp = requests.get(f"{API_URL}/products", params={'query': query}, headers=headers)
        resp.raise_for_status()
        payload = resp.json()
        return payload.get('products', payload)
    except HTTPError as e:
        if e.response.status_code == 401:
            print("🚨 401 Unauthorized from RepairShopr. Check your API key.")
        else:
            print(f"⚠️ RepairShopr API error ({e.response.status_code}): {e}")
    except RequestException as e:
        print(f"⚠️ RepairShopr network error: {e}")
    return []

def search_products(query):
    """
    Returns a list of dicts with:
      id, name, description (<=100 chars), price_cost, price_retail
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
            'price_retail':  float(p.get('price_retail', 0))   # retail :contentReference[oaicite:2]{index=2}
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
