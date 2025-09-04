import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.bundles.utils import search_products
from app.api import repairshopr


class DummyResponse:
    """Minimal response object for mocking ``requests.get``."""

    def __init__(self, data):
        self._data = data
        self.status_code = 200

    def raise_for_status(self):
        """requests.Response compatible stub."""
        return None

    def json(self):
        return self._data


def make_fake_get(responses):
    """Return a ``requests.get`` replacement using ``responses`` mapping."""

    def fake_get(url, params=None, headers=None):
        key, val = next(iter(params.items()))
        data = responses.get(key, {}).get(val, {'products': []})
        return DummyResponse(data)

    return fake_get


def test_search_by_name(monkeypatch):
    responses = {
        'name': {
            'Widget': {
                'products': [
                    {
                        'id': 1,
                        'name': 'Widget',
                        'description': 'A thing',
                        'price_cost': 1,
                        'price_retail': 2,
                    }
                ]
            }
        }
    }
    monkeypatch.setattr(repairshopr.requests, 'get', make_fake_get(responses))
    prods = search_products('Widget')
    assert len(prods) == 1
    assert prods[0]['name'] == 'Widget'
    assert prods[0]['cost'] == 1.0
    assert prods[0]['retail'] == 2.0


def test_description_not_searched(monkeypatch):
    """Description-only matches should not return results."""
    responses = {
        'description': {
            'amazing': {
                'products': [
                    {
                        'id': 2,
                        'name': 'Gizmo',
                        'description': 'An amazing thing',
                        'price_cost': 3,
                        'price_retail': 5,
                    }
                ]
            }
        }
    }
    monkeypatch.setattr(repairshopr.requests, 'get', make_fake_get(responses))
    prods = search_products('amazing')
    assert prods == []


def test_search_by_sku(monkeypatch):
    responses = {
        'sku': {
            'ABC123': {
                'products': [
                    {
                        'id': 3,
                        'name': 'Sku Prod',
                        'description': 'desc',
                        'price_cost': 4,
                        'price_retail': 6,
                    }
                ]
            }
        }
    }
    monkeypatch.setattr(repairshopr.requests, 'get', make_fake_get(responses))
    prods = search_products('ABC123')
    assert len(prods) == 1
    assert prods[0]['id'] == 3
    assert prods[0]['cost'] == 4.0
    assert prods[0]['retail'] == 6.0

