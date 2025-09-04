import os
import time

from app import create_app
from app.inventory_store import init_db, upsert_products, search_products
from app import inventory_sync

# Helper to create app with temp instance path

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
        upsert_products([{'id':1,'name':'Local','upc_code':'12345678','price_retail':1,'price_cost':0}])
        res = search_products('12345678')
        assert res and res[0]['id'] == 1

        called = []
        def fake_bar(code):
            called.append(code)
            return {'id':2,'name':'Remote','upc_code':code,'price_retail':2,'price_cost':1}
        monkeypatch.setattr(inventory_sync, 'fetch_product_by_barcode', fake_bar)
        RF = type('RF',(),{
            'by_barcode': staticmethod(fake_bar),
            'by_sku': staticmethod(lambda s: []),
            'by_query': staticmethod(lambda q: [])
        })
        res = search_products('87654321', remote_fetch=RF)
        assert called == ['87654321']
        assert res[0]['id'] == 2
        # subsequent hit local
        called.clear()
        res = search_products('87654321')
        assert not called
        assert res and res[0]['id'] == 2


def test_sku_local_then_remote(monkeypatch, tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        upsert_products([{'id':1,'name':'Local','sku':'ABC123','price_retail':1,'price_cost':0}])
        res = search_products('ABC123')
        assert res and res[0]['id'] == 1

        called = []
        def fake_sku(sku):
            called.append(sku)
            return [{'id':3,'name':'RemoteSku','sku':sku,'price_retail':3,'price_cost':1}]
        monkeypatch.setattr(inventory_sync, 'fetch_products_by_sku', fake_sku)
        RF = type('RF',(),{
            'by_barcode': staticmethod(lambda b: None),
            'by_sku': staticmethod(fake_sku),
            'by_query': staticmethod(lambda q: [])
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
        rows = [{'id':i,'name':f'Widget {i}','sku':f'W{i}','price_retail':1,'price_cost':0} for i in range(1,31)]
        upsert_products(rows)
        res1 = search_products('Widget', page=1)
        res2 = search_products('Widget', page=2)
        assert len(res1) == 25
        assert len(res2) == 5


def test_token_bucket_throttles():
    bucket = inventory_sync.TokenBucket(capacity=2, refill_per_min=60)
    start = time.monotonic()
    bucket.throttle()
    bucket.throttle()
    bucket.throttle()
    elapsed = time.monotonic() - start
    assert elapsed >= 1.0


def test_admin_sync(monkeypatch, tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()

    def fake_full_sync():
        with app.app_context():
            from app.inventory_store import set_meta
            set_meta('inventory_last_synced_at', 'now')
    import app.admin as admin_module
    monkeypatch.setattr(admin_module, 'full_sync', fake_full_sync)

    res = client.post('/admin/inventory/sync', headers={'X-Admin-Secret':'s3cr3t'})
    assert res.status_code == 200
    for _ in range(50):
        status = client.get('/admin/inventory/status', headers={'X-Admin-Secret':'s3cr3t'}).get_json()
        if not status['running']:
            break
        time.sleep(0.1)
    assert status['running'] is False
    assert status['last_synced_at'] == 'now'
