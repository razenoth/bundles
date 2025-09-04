# app/admin.py
"""Simple admin blueprint for manual inventory sync."""

import os
import threading
import csv
import io
import json
from flask import (
    Blueprint,
    jsonify,
    render_template,
    request,
    abort,
    current_app,
    make_response,
)

from .inventory_store import get_meta, list_products, ro_conn
from .inventory_sync import full_sync

bp = Blueprint('admin', __name__, template_folder='templates/admin')

ADMIN_SECRET = os.environ.get('ADMIN_SECRET')
_sync_running = False


def _check_secret():
    if ADMIN_SECRET and request.headers.get('X-Admin-Secret') != ADMIN_SECRET:
        abort(403)


@bp.before_request
def before():
    _check_secret()


@bp.route('/inventory')
def inventory_page():
    last = get_meta('inventory_last_synced_at', 'never')
    return render_template('admin/inventory.html', last=last, secret=ADMIN_SECRET or '')


@bp.route('/inventory/sync', methods=['POST'])
def inventory_sync():
    global _sync_running
    if _sync_running:
        return jsonify(started=False), 409

    app = current_app._get_current_object()

    def runner():
        global _sync_running
        _sync_running = True
        try:
            with app.app_context():
                full_sync()
        finally:
            _sync_running = False

    threading.Thread(target=runner, daemon=True).start()
    return jsonify(started=True)


@bp.route('/inventory/status')
def inventory_status():
    last = get_meta('inventory_last_synced_at')
    return jsonify(last_synced_at=last, running=_sync_running)


@bp.route('/inventory/products')
def inventory_products():
    """Expose a subset of the mirrored products for admin inspection."""
    prods = list_products()
    return jsonify(products=prods)


@bp.route('/inventory/products.csv')
def inventory_products_csv():
    """Download the mirrored products as a CSV file."""
    with ro_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, sku, raw_json FROM products ORDER BY id"
        ).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "sku", "quantity"])
    for r in rows:
        raw = json.loads(r["raw_json"] or "{}")
        qty = (
            raw.get("quantity_on_hand")
            or raw.get("quantity")
            or raw.get("qty")
            or 0
        )
        writer.writerow([r["id"], r["name"], r["sku"], qty])
    resp = make_response(output.getvalue())
    resp.headers["Content-Disposition"] = "attachment; filename=inventory.csv"
    resp.mimetype = "text/csv"
    return resp
