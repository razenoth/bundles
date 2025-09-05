import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Estimate, EstimateItem
from app.api import repairshopr as rs_api


def setup_app():
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    app = create_app('development')
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app


def test_push_creates_estimate(monkeypatch):
    app = setup_app()
    with app.app_context():
        est = Estimate(customer_id=1, customer_name='Cust', customer_address='A')
        db.session.add(est)
        db.session.commit()
        item = EstimateItem(
            estimate_id=est.id,
            type='product',
            object_id=42,
            name='Widget',
            description='',
            quantity=2,
            unit_price=10.0,
            retail=15.0,
        )
        db.session.add(item)
        db.session.commit()

        called = {}

        def fake_last():
            return {'number': '100'}

        def fake_create(customer_id, line_items, number=None):
            called['args'] = (customer_id, line_items, number)
            return {'id': 555}

        monkeypatch.setattr(rs_api, 'get_last_estimate', fake_last)
        monkeypatch.setattr(rs_api, 'create_estimate', fake_create)

        client = app.test_client()
        resp = client.post(f'/estimates/{est.id}/push')
        assert resp.status_code == 200
        assert called['args'][0] == 1
        assert called['args'][1][0]['name'] == 'Widget'
        assert called['args'][2] == 101
