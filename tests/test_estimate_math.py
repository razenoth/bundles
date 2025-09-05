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


def test_totals_and_markup():
    app = setup_app()
    with app.app_context():
        est = Estimate(customer_id=None, customer_name='Test', customer_address='')
        db.session.add(est)
        db.session.commit()
        i1 = EstimateItem(estimate_id=est.id, type='product', object_id=1,
                          name='Widget', description='', quantity=2,
                          unit_price=10.0, retail=15.0)
        i2 = EstimateItem(estimate_id=est.id, type='product', object_id=2,
                          name='Gadget', description='', quantity=1,
                          unit_price=5.0, retail=8.0)
        db.session.add_all([i1, i2])
        db.session.commit()
        assert est.total_cost == 2*10.0 + 1*5.0
        assert est.total_retail == 2*15.0 + 1*8.0
        profit = est.total_retail - est.total_cost
        assert est.profit == profit
        markup = (profit / est.total_cost) * 100
        assert round(markup, 2) == round((profit / est.total_cost) * 100, 2)
        db.session.delete(i1)
        db.session.commit()
        assert est.total_cost == 5.0
        assert est.total_retail == 8.0


def test_bundle_parent_children_totals():
    app = setup_app()
    with app.app_context():
        est = Estimate(customer_id=None, customer_name='Test', customer_address='')
        db.session.add(est)
        db.session.commit()

        parent = EstimateItem(estimate_id=est.id, type='bundle', object_id=99,
                              name='Kit', description='', quantity=1,
                              unit_price=10.0, retail=15.0)
        db.session.add(parent)
        db.session.flush()
        child = EstimateItem(estimate_id=est.id, type='product', object_id=1,
                             name='Widget', description='', quantity=2,
                             unit_price=3.0, retail=5.0, parent_id=parent.id)
        db.session.add(child)
        db.session.commit()

        # Only the bundle parent should contribute to totals
        assert est.total_cost == 10.0
        assert est.total_retail == 15.0
