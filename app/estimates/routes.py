from flask import Blueprint, render_template, request, jsonify, url_for, redirect, flash
from app import db
from app.models import Estimate, EstimateItem, Bundle
from app.estimates.utils import (
    search_products,
    search_customers_util,
    clone_bundle_to_items
)

bp = Blueprint('estimates', __name__)  # will use app/templates/estimates/*.html

@bp.route('/')
def list_estimates():
    ests = Estimate.query.order_by(Estimate.id.desc()).all()
    return render_template('estimates/list.html', estimates=ests)

@bp.route('/<int:estimate_id>')
def view_estimate(estimate_id):
    est = Estimate.query.get_or_404(estimate_id)
    return render_template('estimates/view.html', estimate=est)

@bp.route('/<int:estimate_id>/delete', methods=['POST'])
def delete_estimate(estimate_id):
    est = Estimate.query.get_or_404(estimate_id)
    db.session.delete(est)
    db.session.commit()
    flash('Estimate deleted', 'success')
    return redirect(url_for('estimates.list_estimates'))

@bp.route('/create', methods=['GET'])
def create_estimate():
    """Auto-create an empty draft and redirect to its edit form."""
    est = Estimate(
        customer_id      = None,
        customer_name    = '',
        customer_address = '',
        status           = 'draft'
    )
    db.session.add(est)
    db.session.commit()
    return redirect(url_for('estimates.edit_estimate', estimate_id=est.id))

@bp.route('/<int:estimate_id>/edit', methods=['GET', 'POST'])
def edit_estimate(estimate_id):
    est = Estimate.query.get_or_404(estimate_id)
    if request.method == 'POST':
        data = request.get_json() or request.form
        est.customer_id      = data['customer_id']
        est.customer_name    = data['customer_name']
        est.customer_address = data.get('customer_address')
        est.status           = data.get('status', est.status)
        db.session.commit()
        return jsonify(success=True)
    return render_template('estimates/form.html', estimate=est)

@bp.route('/search-customer')
def search_customer():
    q = request.args.get('q', '')
    results = search_customers_util(q)
    return jsonify(customers=results)

@bp.route('/search')
def search_for_items():
    q = request.args.get('q', '')
    prods   = search_products(q)
    bundles = Bundle.query.filter(Bundle.name.ilike(f'%{q}%')).all()
    b_list  = [{'id': b.id, 'name': b.name, 'type': 'bundle'} for b in bundles]
    return jsonify({'products': prods, 'bundles': b_list})

@bp.route('/<int:estimate_id>/add-item', methods=['POST'])
def add_estimate_item(estimate_id):
    data = request.get_json()
    est  = Estimate.query.get_or_404(estimate_id)

    if data.get('type') == 'bundle':
        bundle = Bundle.query.get_or_404(data['id'])
        items  = clone_bundle_to_items(bundle, est)
        db.session.add_all(items)
        db.session.commit()
        return jsonify(success=True, added=[i.id for i in items])

    it = EstimateItem(
        estimate_id = estimate_id,
        type        = data['type'],
        object_id   = data['id'],
        name        = data['name'],
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
