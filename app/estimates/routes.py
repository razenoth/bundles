# app/estimates/routes.py

from flask import Blueprint, render_template, request, jsonify, url_for, redirect, flash
from app import db
from app.models import Estimate, EstimateItem, Bundle
from app.estimates.utils import (
    search_products,
    search_customers_util,
    clone_bundle_to_items,
    search_bundles,
)

bp = Blueprint('estimates', __name__, template_folder='templates/estimates')


@bp.route('/')
def list_estimates():
    ests = Estimate.query.order_by(Estimate.id.desc()).all()
    return render_template('list.html', estimates=ests)


@bp.route('/<int:estimate_id>')
def view_estimate(estimate_id):
    est = Estimate.query.get_or_404(estimate_id)
    return render_template('view.html', estimate=est)


@bp.route('/create', methods=['GET'])
def create_estimate():
    """Create a new draft estimate and redirect into its edit form."""
    est = Estimate(customer_id=None, customer_name='', customer_address='', status='draft')
    db.session.add(est)
    db.session.commit()
    return redirect(url_for('estimates.edit_estimate', estimate_id=est.id))


@bp.route('/<int:estimate_id>/edit', methods=['GET', 'POST'])
def edit_estimate(estimate_id):
    est = Estimate.query.get_or_404(estimate_id)
    if request.method == 'POST':
        data = request.get_json() or request.form
        est.customer_id      = data.get('customer_id')
        est.customer_name    = data.get('customer_name')
        est.customer_address = data.get('customer_address', est.customer_address)
        est.status           = data.get('status', est.status)
        db.session.commit()
        return jsonify(success=True)
    return render_template('form.html', estimate=est)


@bp.route('/search-customer')
def search_customer():
    q = request.args.get('q', '')
    results = search_customers_util(q)
    return jsonify(customers=results)


@bp.route('/search')
def search_for_items():
    """
    Product-only search for the Estimates page.
    Returns { products: [ {id,name,description,unit_price,retail,type}, … ] }.
    """
    q = request.args.get('q', '')
    prods = search_products(q)
    return jsonify(products=prods)


@bp.route('/bundles/search')
def search_bundles_endpoint():
    """
    Bundle-only search for the Estimates page.
    Returns { bundles: [ {id,name,description,cost,retail,type}, … ] }.
    """
    q = request.args.get('q', '')
    blst = search_bundles(q)
    return jsonify(bundles=blst)


@bp.route('/bundles/<int:bundle_id>/clone')
def clone_bundle_endpoint(bundle_id):
    """
    Clone a saved bundle’s items for client‐side addition.
    Optional ?qty= multiplier to scale all line-item quantities.
    Returns { items: [ {id,name,description,quantity,unit_price,retail,type}, … ] }.
    """
    qty = int(request.args.get('qty', 1))
    bundle = Bundle.query.get_or_404(bundle_id)
    items = clone_bundle_to_items(bundle, None)
    for it in items:
        it.quantity *= qty
    serialized = []
    for it in items:
        serialized.append({
            'id'          : it.object_id,
            'name'        : it.name,
            'description' : it.description or '',
            'quantity'    : it.quantity,
            'unit_price'  : it.unit_price,
            'retail'      : it.retail,
            'type'        : 'product'
        })
    return jsonify(items=serialized)


@bp.route('/<int:estimate_id>/add-item', methods=['POST'])
def add_estimate_item(estimate_id):
    """
    Add either a single product or an entire bundle (legacy path) into an estimate.
    """
    data = request.get_json()
    est  = Estimate.query.get_or_404(estimate_id)

    if data.get('type') == 'bundle':
        bundle = Bundle.query.get_or_404(data['id'])
        qty    = data.get('quantity', 1)
        items  = clone_bundle_to_items(bundle, est)
        for it in items:
            it.quantity *= qty
        db.session.add_all(items)
        db.session.commit()
        return jsonify(success=True, added=[i.id for i in items])

    # single product
    it = EstimateItem(
        estimate_id = estimate_id,
        type        = data.get('type'),
        object_id   = data.get('id'),
        name        = data.get('name'),
        description = data.get('description'),
        quantity    = data.get('quantity', 1),
        unit_price  = data.get('unit_price', 0.0),
        retail      = data.get('retail', data.get('unit_price', 0.0)),
        notes       = data.get('notes', '')
    )
    db.session.add(it)
    db.session.commit()
    return jsonify(item_id=it.id, success=True)


@bp.route('/<int:estimate_id>/remove-item/<int:item_id>', methods=['POST'])
def remove_estimate_item(estimate_id, item_id):
    it = EstimateItem.query.get_or_404(item_id)
    db.session.delete(it)
    db.session.commit()
    return jsonify(success=True)


@bp.route('/<int:estimate_id>/update-item/<int:item_id>', methods=['POST'])
def update_estimate_item(estimate_id, item_id):
    data = request.get_json()
    it   = EstimateItem.query.get_or_404(item_id)
    it.quantity   = data.get('quantity', it.quantity)
    it.unit_price = data.get('unit_price', it.unit_price)
    it.retail     = data.get('retail', it.retail)
    it.notes      = data.get('notes', it.notes)
    db.session.commit()
    return jsonify(success=True)
