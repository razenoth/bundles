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
        resp = requests.get(f"{API_URL}/products", params={'search': query}, headers=headers)
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
