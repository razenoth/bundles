# app/api/repairshopr.py
import os
import requests
from requests.exceptions import HTTPError, RequestException

# Base URL: either override via env or build from subdomain
API_URL = os.getenv('REPAIRSHOPR_API_URL') or \
          f"https://{os.getenv('REPAIRSHOPR_SUBDOMAIN')}.repairshopr.com/api/v1"
# This should be the session_token (Bearer) you get from your RepairShopr account
API_KEY = os.getenv('REPAIRSHOPR_API_KEY')

def get_products(query):
    """Returns a list of product dicts from RepairShopr matching `query`."""
    # Use Bearer auth per swagger's bearerAuth scheme :contentReference[oaicite:2]{index=2}
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Accept': 'application/json'
    }
    try:
        # Hit the search endpoint
        resp = requests.get(
            f"{API_URL}/products/search",
            params={'query': query},
            headers=headers,
            timeout=5
        )
        # If your instance doesn't support /products/search, fallback:
        if resp.status_code == 404:
            resp = requests.get(
                f"{API_URL}/products",
                params={'query': query},
                headers=headers,
                timeout=5
            )
        # Will raise HTTPError on 4xx/5xx
        resp.raise_for_status()

        payload = resp.json()
        # swagger shows top‐level “products” array for this call :contentReference[oaicite:3]{index=3}
        return payload.get('products', payload)
    except HTTPError as e:
        if e.response.status_code == 401:
            print(
                "🚨 401 Unauthorized from RepairShopr. "
                "Double-check your REPAIRSHOPR_API_KEY in .env "
                "(should be your session_token/Bearer token)."
            )
        else:
            print(f"⚠️ RepairShopr API error ({e.response.status_code}): {e}")
    except RequestException as e:
        print(f"⚠️ RepairShopr network error: {e}")
    return []
