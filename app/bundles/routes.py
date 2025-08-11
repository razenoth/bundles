# app/bundles/routes.py

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Bundle, BundleItem
from app.bundles.utils import search_products

bp = Blueprint('bundles', __name__, template_folder='templates/bundles')

@bp.route('/', methods=['GET'])
def list_bundles():
    bundles = Bundle.query.order_by(Bundle.name).all()
    return render_template('bundles/list.html', bundles=bundles)

@bp.route('/create', methods=['GET', 'POST'])
def create_bundle():
    if request.method == 'POST':
        name        = request.form['name'].strip()
        description = request.form.get('description', '').strip()
        if not name:
            flash('Bundle name required', 'warning')
        else:
            b = Bundle(name=name, description=description)
            db.session.add(b)
            try:
                db.session.commit()
                return redirect(url_for('bundles.edit_bundle', bundle_id=b.id))
            except IntegrityError:
                db.session.rollback()
                flash('Bundle name already exists', 'danger')
    return render_template('bundles/create.html')

@bp.route('/<int:bundle_id>/edit', methods=['GET', 'POST'])
def edit_bundle(bundle_id):
    bundle = Bundle.query.get_or_404(bundle_id)

    # Handle updates to bundle name/description
    if request.method == 'POST' and 'name' in request.form:
        name        = request.form['name'].strip()
        description = request.form.get('description', '').strip()
        if not name:
            flash('Name cannot be empty', 'warning')
        else:
            bundle.name        = name
            bundle.description = description
            db.session.commit()
            flash('Bundle updated', 'success')
        return redirect(url_for('bundles.edit_bundle', bundle_id=bundle.id))

    # GET: render edit page with totals
    total_cost   = sum(i.unit_price * i.quantity   for i in bundle.items)
    total_retail = sum(i.retail * i.quantity for i in bundle.items)
    return render_template(
        'bundles/edit.html',
        bundle=bundle,
        total_cost=total_cost,
        total_retail=total_retail
    )

@bp.route('/<int:bundle_id>/delete', methods=['POST'])
def delete_bundle(bundle_id):
    bundle = Bundle.query.get_or_404(bundle_id)

    # 1) Delete all child items first to avoid FK constraint errors
    db.session.query(BundleItem).filter_by(bundle_id=bundle.id).delete()

    # 2) Now delete the bundle itself
    db.session.delete(bundle)
    db.session.commit()

    flash(f"Bundle '{bundle.name}' and its items deleted", 'success')
    return redirect(url_for('bundles.list_bundles'))

@bp.route('/search')
def bundles_search():
    q = request.args.get('q', '')
    products = search_products(q)
    return jsonify(products=products)

@bp.route('/<int:bundle_id>/add-item', methods=['POST'])
def add_bundle_item(bundle_id):
    data   = request.get_json()
    bundle = Bundle.query.get_or_404(bundle_id)

    if data.get('type') != 'product':
        return jsonify(error='Invalid type'), 400

    prod = next((p for p in search_products(data['q'])
                 if str(p['id']) == str(data['id'])), None)
    if not prod:
        return jsonify(error='Not found'), 404

    it = BundleItem(
        bundle_id    = bundle.id,
        product_name = prod['name'],
        description  = prod['description'],
        quantity     = data.get('quantity', 1),
        unit_price   = prod.get('cost', 0),
        retail       = prod.get('retail', 0)
    )
    db.session.add(it)
    db.session.commit()
    return jsonify(success=True, item_id=it.id)

@bp.route('/<int:bundle_id>/remove-item/<int:item_id>', methods=['POST'])
def remove_bundle_item(bundle_id, item_id):
    it = BundleItem.query.get_or_404(item_id)
    db.session.delete(it)
    db.session.commit()
    return jsonify(success=True)

@bp.route('/<int:bundle_id>/update-item/<int:item_id>', methods=['POST'])
def update_bundle_item(bundle_id, item_id):
    data = request.get_json()
    it   = BundleItem.query.get_or_404(item_id)
    it.quantity    = int(data.get('quantity', it.quantity))
    it.unit_price        = float(data.get('cost', it.unit_price))
    it.retail      = float(data.get('retail', it.retail))
    it.description = data.get('description', it.description)
    db.session.commit()
    return jsonify(success=True)

@bp.route('/search-bundles')
def search_bundles():
    """
    AJAX endpoint for saved-bundle search.
    Returns JSON: { bundles: [ { id, name, description, cost, retail, type }, … ] }
    """
    q = request.args.get('q', '').strip()
    term = f"%{q}%"
    bundles = Bundle.query.filter(Bundle.name.ilike(term)).all() if q else []
    results = []
    for b in bundles:
        total_cost   = sum(item.unit_price for item in b.items)
        total_retail = sum(item.retail     for item in b.items)
        results.append({
            'id'          : b.id,
            'name'        : b.name,
            'description' : (b.description or '')[:100],
            'cost'        : float(total_cost),
            'retail'      : float(total_retail),
            'type'        : 'bundle'
        })
    return jsonify(bundles=results)
