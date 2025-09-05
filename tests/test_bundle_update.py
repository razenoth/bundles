import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Bundle, BundleItem


def setup_app():
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    app = create_app('development')
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app


def test_refresh_bundle_updates_cost(monkeypatch):
    app = setup_app()
    with app.app_context():
        b = Bundle(name='Test', description='')
        item = BundleItem(bundle=b, product_name='Widget', description='',
                          quantity=1, unit_price=5.0, retail=10.0)
        db.session.add_all([b, item])
        db.session.commit()

        def fake_search_products(q, page=1):
            return [{'id': 1, 'name': 'Widget', 'description': '',
                     'cost': 7.5, 'retail': 10.0, 'stock': 3, 'type': 'product'}]

        monkeypatch.setattr('app.bundles.routes.search_products', fake_search_products)

        client = app.test_client()
        resp = client.post(f'/bundles/{b.id}/refresh')
        assert resp.status_code == 200
        db.session.refresh(item)
        assert item.unit_price == 7.5
