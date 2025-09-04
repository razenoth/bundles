import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.inventory_store import init_db


def make_app(tmp_path):
    os.environ.setdefault('REPAIRSHOPR_SUBDOMAIN', 'test')
    os.environ.setdefault('REPAIRSHOPR_API_KEY', 'key')
    app = create_app('development')
    app.instance_path = str(tmp_path)
    os.makedirs(app.instance_path, exist_ok=True)
    with app.app_context():
        init_db()
    return app


def test_admin_link_in_nav(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    res = client.get('/bundles/')
    assert b'/admin/inventory' in res.data
