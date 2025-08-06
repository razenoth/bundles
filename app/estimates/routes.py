from flask import Blueprint, render_template, request, jsonify, url_for, redirect, flash
from app import db
from app.models import Estimate, EstimateItem, Bundle
from app.estimates.utils import search_products, clone_bundle_to_items

bp = Blueprint('estimates', __name__, template_folder='templates/estimates')

@bp.route('/')
def list_estimates():
    ests = Estimate.query.all()
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
    flash('Estimate deleted','success')
    return redirect(url_for('estimates.list_estimates'))

@bp.route('/search')
def search_for_items():
    q = request.args.get('q','')
    prods = search_products(q)
    bundles = Bundle.query.filter(Bundle.name.ilike(f'%{q}%')).all()
    b_list = [{'id':b.id,'name':b.name,'type':'bundle'} for b in bundles]
    return jsonify({'products':prods,'bundles':b_list})

@bp.route('/<int:estimate_id>/add-item', methods=['POST'])
def add_estimate_item(estimate_id):
    data = request.get_json()
    est = Estimate.query.get_or_404(estimate_id)
    if data.get('type')=='bundle':
        bundle = Bundle.query.get_or_404(data['id'])
        items = clone_bundle_to_items(bundle, est)
        db.session.add_all(items)
    else:
        prod = search_products(data.get('name',''))[0]
        db.session.add(EstimateItem(
            estimate_id=est.id,
            description=prod['name'],
            quantity=1,
            unit_price=prod['unit_price']
        ))
    db.session.commit()
    return jsonify(success=True)

@bp.route('/<int:estimate_id>/remove-item/<int:item_id>', methods=['POST'])
def remove_estimate_item(estimate_id, item_id):
    it = EstimateItem.query.get_or_404(item_id)
    db.session.delete(it)
    db.session.commit()
    return jsonify(success=True)

@bp.route('/<int:estimate_id>/update-item/<int:item_id>', methods=['POST'])
def update_estimate_item(estimate_id, item_id):
    data = request.get_json()
    it = EstimateItem.query.get_or_404(item_id)
    it.quantity   = data.get('quantity', it.quantity)
    it.unit_price = data.get('unit_price', it.unit_price)
    it.notes      = data.get('notes', it.notes)
    db.session.commit()
    return jsonify(success=True)
