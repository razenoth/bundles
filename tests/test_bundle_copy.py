import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Bundle, BundleItem, Estimate, EstimateItem


def setup_app():
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    app = create_app('development')
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app


def copy_bundle(bundle, estimate):
    for bi in bundle.items:
        ei = EstimateItem(
            estimate_id=estimate.id,
            type='product',
            object_id=bi.id,
            name=bi.product_name,
            description=bi.description,
            quantity=bi.quantity,
            unit_price=bi.unit_price,
            retail=bi.retail,
        )
        db.session.add(ei)
    db.session.commit()


def test_bundle_copy_is_snapshot():
    app = setup_app()
    with app.app_context():
        b = Bundle(name='Starter', description='')
        bi = BundleItem(bundle=b, product_name='Widget', description='',
                        quantity=1, unit_price=10.0, retail=15.0)
        db.session.add_all([b, bi])
        db.session.commit()
        est = Estimate(customer_id=None, customer_name='Cust', customer_address='')
        db.session.add(est)
        db.session.commit()
        copy_bundle(b, est)
        line = EstimateItem.query.filter_by(estimate_id=est.id).first()
        assert line.unit_price == 10.0
        # mutate bundle item after copying
        bi.unit_price = 999.0
        db.session.commit()
        line_after = EstimateItem.query.filter_by(estimate_id=est.id).first()
        assert line_after.unit_price == 10.0
