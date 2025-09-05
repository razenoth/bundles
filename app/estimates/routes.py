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

# No more template_folder; use the app's templates/estimates directory
bp = Blueprint('estimates', __name__, url_prefix='/estimates')


@bp.route('/')
def list_estimates():
    ests = Estimate.query.order_by(Estimate.id.desc()).all()
    return render_template('estimates/list.html', estimates=ests)


@bp.route('/<int:estimate_id>')
def view_estimate(estimate_id):
    est = Estimate.query.get_or_404(estimate_id)
    return render_template('estimates/view.html', estimate=est)


@bp.route('/create', methods=['GET'])
def create_estimate():
    """Auto-create a draft and redirect into its editor."""
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

    top_items = EstimateItem.query.filter_by(estimate_id=est.id, parent_id=None).all()
    return render_template('estimates/form.html', estimate=est, items=top_items)


@bp.route('/search-customer')
def search_customer():
    q = request.args.get('q', '')
    results = search_customers_util(q)
    return jsonify(customers=results)


@bp.route('/search')
def search_for_items():
    """
    Product-only search.
    Returns { products: [ {id,name,description,unit_price,retail,type}, … ] }.
    """
    q = request.args.get('q', '')
    page = int(request.args.get('page', 1))
    prods = search_products(q, page=page)
    return jsonify(products=prods)


@bp.route('/bundles/search')
def search_bundles_endpoint():
    """
    Bundle-only search.
    Returns { bundles: [ {id,name,description,cost,retail,type}, … ] }.
    """
    q = request.args.get('q', '')
    blst = search_bundles(q)
    return jsonify(bundles=blst)


@bp.route('/bundles/<int:bundle_id>/clone')
def clone_bundle_endpoint(bundle_id):
    """
    Clone a saved bundle’s items for client-side addition.
    Optional ?qty= to scale line-item quantities.
    Returns { items: [ {id,name,description,quantity,unit_price,retail,type}, … ] }.
    """
    qty = int(request.args.get('qty', 1))
    bundle = Bundle.query.get_or_404(bundle_id)
    items  = clone_bundle_to_items(bundle, None)
    for it in items:
        it.quantity *= qty
    serialized = [{
        'id'          : it.object_id,
        'name'        : it.name,
        'description' : it.description or '',
        'quantity'    : it.quantity,
        'unit_price'  : it.unit_price,
        'retail'      : it.retail,
        'type'        : 'product'
    } for it in items]
    return jsonify(items=serialized)


@bp.route('/<int:estimate_id>/add-item', methods=['POST'])
def add_estimate_item(estimate_id):
    data = request.get_json()
    est  = Estimate.query.get_or_404(estimate_id)

    if data.get('type') == 'bundle':
        bundle = Bundle.query.get_or_404(data['id'])
        qty    = int(data.get('quantity', 1))
        cloned = clone_bundle_to_items(bundle, None)
        total_cost   = sum(it.unit_price * it.quantity for it in cloned)
        total_retail = sum(it.retail * it.quantity for it in cloned)

        parent = EstimateItem(
            estimate_id = estimate_id,
            type        = 'bundle',
            object_id   = bundle.id,
            name        = bundle.name,
            description = bundle.description,
            quantity    = qty,
            unit_price  = total_cost,
            retail      = total_retail,
        )
        db.session.add(parent)
        db.session.flush()  # obtain parent.id

        items = []
        for it in cloned:
            it.estimate_id = estimate_id
            it.quantity   *= qty
            it.parent_id   = parent.id
            items.append(it)
        db.session.add_all(items)
        db.session.commit()

        return jsonify(
            parent={
                'id'        : parent.id,
                'name'      : parent.name,
                'quantity'  : parent.quantity,
                'unit_price': parent.unit_price,
                'retail'    : parent.retail,
            },
            items=[{
                'id'        : i.id,
                'name'      : i.name,
                'quantity'  : i.quantity,
                'unit_price': i.unit_price,
                'retail'    : i.retail,
                'parent_id' : i.parent_id
            } for i in items]
        )

    # Single-product path
    it = EstimateItem(
        estimate_id = estimate_id,
        type        = data.get('type'),
        object_id   = data.get('id'),
        name        = data.get('name'),
        description = data.get('description'),
        quantity    = data.get('quantity', 1),
        unit_price  = data.get('unit_price', 0.0),
        retail      = data.get('retail', data.get('unit_price', 0.0)),
        notes       = data.get('notes', ''),
        parent_id   = data.get('parent_id')
    )
    db.session.add(it)
    db.session.commit()
    return jsonify(item_id=it.id, success=True)


@bp.route('/<int:estimate_id>/remove-item/<int:item_id>', methods=['POST'])
def remove_estimate_item(estimate_id, item_id):
    it = EstimateItem.query.get_or_404(item_id)
    # delete children if removing a bundle parent
    for child in list(it.children):
        db.session.delete(child)
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


@bp.route('/<int:estimate_id>/refresh', methods=['POST'])
def refresh_estimate(estimate_id):
    """Update line items with current cost from RepairShopr."""
    est = Estimate.query.get_or_404(estimate_id)
    updated = []
    for it in est.items:
        if it.type != 'product':
            continue
        prod = next((p for p in search_products(it.name)
                     if p.get('name') == it.name), None)
        if prod:
            new_cost = prod.get('unit_price', it.unit_price)
            it.unit_price = new_cost
            updated.append({
                'id': it.id,
                'unit_price': new_cost,
            })
    # Recalculate parent bundle lines
    for parent in [i for i in est.items if i.type == 'bundle']:
        total_cost   = sum(ch.quantity * ch.unit_price for ch in parent.children)
        total_retail = sum(ch.quantity * ch.retail for ch in parent.children)
        parent.unit_price = total_cost
        parent.retail     = total_retail
        updated.append({
            'id': parent.id,
            'unit_price': parent.unit_price,
            'retail': parent.retail,
        })
    db.session.commit()
    return jsonify(items=updated)

@bp.route('/<int:estimate_id>/delete', methods=['POST'])
def delete_estimate(estimate_id):
    """
    Delete an estimate and redirect back to the list view.
    """
    est = Estimate.query.get_or_404(estimate_id)
    db.session.delete(est)
    db.session.commit()
    flash(f'Estimate #{estimate_id} deleted', 'success')
    return redirect(url_for('estimates.list_estimates'))
