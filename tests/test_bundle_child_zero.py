import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Estimate, EstimateItem


def setup_app():
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    app = create_app('development')
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app


def test_child_qty_zero_updates_parent():
    app = setup_app()
    with app.app_context():
        est = Estimate(customer_id=None, customer_name='Test', customer_address='')
        db.session.add(est)
        db.session.commit()
        parent = EstimateItem(estimate_id=est.id, type='bundle', object_id=1,
                              name='Kit', description='', quantity=1,
                              unit_price=5.0, retail=10.0)
        db.session.add(parent)
        db.session.flush()
        child = EstimateItem(estimate_id=est.id, type='product', object_id=2,
                             name='Widget', description='', quantity=1,
                             unit_price=5.0, retail=10.0, parent_id=parent.id)
        db.session.add(child)
        db.session.commit()

        client = app.test_client()
        resp = client.post(f'/estimates/{est.id}/update-item/{child.id}',
                           json={'quantity': 0})
        assert resp.status_code == 200
        db.session.refresh(parent)
        assert parent.unit_price == 0
        assert parent.retail == 0
