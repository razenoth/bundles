import os
import sys
import time

# Ensure env vars available during module import
os.environ.setdefault('REPAIRSHOPR_SUBDOMAIN', 'test')
os.environ.setdefault('REPAIRSHOPR_API_KEY', 'key')
os.environ.setdefault('ADMIN_SECRET', 's3cr3t')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.inventory_store import (
    init_db,
    upsert_products,
    search_products,
    get_sync_state,
    set_sync_state,
)
from app import inventory_sync
from app.repairshopr_client import TokenBucket


def make_app(tmp_path):
    os.environ.setdefault('REPAIRSHOPR_SUBDOMAIN', 'test')
    os.environ.setdefault('REPAIRSHOPR_API_KEY', 'key')
    os.environ.setdefault('ADMIN_SECRET', 's3cr3t')
    app = create_app('development')
    app.instance_path = str(tmp_path)
    os.makedirs(app.instance_path, exist_ok=True)
    with app.app_context():
        init_db()
    return app


def test_upc_local_then_remote(monkeypatch, tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        upsert_products([
            {'id': 1, 'name': 'Local', 'upc_code': '12345678', 'price': 1, 'active': True},
        ])
        res = search_products('12345678')
        assert res and res[0]['id'] == 1

        called = []

        def fake_bar(code):
            called.append(code)
            return {'id': 2, 'name': 'Remote', 'upc_code': code, 'price': 2, 'active': True}

        RF = type('RF', (), {
            'by_barcode': staticmethod(fake_bar),
            'by_sku': staticmethod(lambda s: []),
            'by_query': staticmethod(lambda q: []),
        })
        res = search_products('87654321', remote_fetch=RF)
        assert called == ['87654321']
        assert res[0]['id'] == 2
        # subsequent hit local
        called.clear()
        res = search_products('87654321')
        assert not called and res[0]['id'] == 2


def test_sku_local_then_remote(monkeypatch, tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        upsert_products([
            {'id': 1, 'name': 'Local', 'sku': 'ABC123', 'price': 1, 'active': True},
        ])
        res = search_products('ABC123')
        assert res and res[0]['id'] == 1

        called = []

        def fake_sku(sku):
            called.append(sku)
            return [{'id': 3, 'name': 'RemoteSku', 'sku': sku, 'price': 3, 'active': True}]

        RF = type('RF', (), {
            'by_barcode': staticmethod(lambda b: None),
            'by_sku': staticmethod(fake_sku),
            'by_query': staticmethod(lambda q: []),
        })
        res = search_products('DEF456', remote_fetch=RF)
        assert called == ['DEF456']
        assert res[0]['id'] == 3
        called.clear()
        res = search_products('DEF456')
        assert not called and res[0]['id'] == 3


def test_fts_limit_offset(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        rows = [
            {'id': i, 'name': f'Widget {i}', 'sku': f'W{i}', 'price': 1, 'active': True}
            for i in range(1, 31)
        ]
        upsert_products(rows)
        res1 = search_products('Widget', page=1)
        res2 = search_products('Widget', page=2)
        assert len(res1) == 25
        assert len(res2) == 5


def test_token_bucket_throttles():
    bucket = TokenBucket(capacity=2, refill_per_min=120)  # ~2 rps
    start = time.monotonic()
    bucket.acquire()
    bucket.acquire()
    bucket.acquire()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.5


def test_full_sync_pagination(monkeypatch, tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        pages = [
            [{'id': i, 'name': f'P{i}', 'price': 1, 'active': True} for i in range(1, 26)],
            [{'id': i, 'name': f'P{i}', 'price': 1, 'active': True} for i in range(26, 51)],
            [{'id': i, 'name': f'P{i}', 'price': 1, 'active': True} for i in range(51, 58)],
        ]
        calls = []

        def fake_fetch(page, sort="id ASC"):
            calls.append(page)
            return pages[page - 1] if page - 1 < len(pages) else []

        monkeypatch.setattr(inventory_sync, 'fetch_products_page', fake_fetch)
        res = inventory_sync.full_sync()
        assert res['total'] == 57
        st = get_sync_state()
        assert st['max_product_id_seen'] == 57
        assert calls == [1, 2, 3]


def test_quick_update_new_and_audit(monkeypatch, tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        upsert_products([
            {'id': 1, 'name': 'Old', 'price': 0, 'active': True}
        ])
        set_sync_state({'max_product_id_seen': 50, 'next_audit_page': 1})
        calls = []

        def fake_fetch(page, sort="id ASC"):
            calls.append((page, sort))
            if sort == 'id DESC':
                return [
                    {'id': 60, 'name': 'N1', 'price': 1, 'active': True},
                    {'id': 55, 'name': 'N2', 'price': 1, 'active': True},
                    {'id': 45, 'name': 'N3', 'price': 1, 'active': True},
                ]
            else:  # audit
                return [{'id': 1, 'name': 'New', 'price': 0, 'active': True}]

        monkeypatch.setattr(inventory_sync, 'fetch_products_page', fake_fetch)
        res = inventory_sync.quick_update(k_pages=1)
        assert res['new'] == 2
        assert res['updated'] == 1
        assert res['checked'] == 1
        st = get_sync_state()
        assert st['max_product_id_seen'] == 60
        assert st['next_audit_page'] == 1
        # only one descending page call
        assert [c for c in calls if c[1] == 'id DESC'] == [(1, 'id DESC')]


def test_next_audit_wrap(monkeypatch, tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        set_sync_state({'max_product_id_seen': 0, 'next_audit_page': 5})

        def fake_fetch(page, sort="id ASC"):
            if sort == 'id DESC':
                return []
            # audit call returns < PAGE_SIZE to force wrap
            return [{'id': 1, 'name': 'X', 'price': 0, 'active': True}]

        monkeypatch.setattr(inventory_sync, 'fetch_products_page', fake_fetch)
        inventory_sync.quick_update(k_pages=1)
        st = get_sync_state()
        assert st['next_audit_page'] == 1

