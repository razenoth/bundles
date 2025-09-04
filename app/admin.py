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

from .inventory_store import get_meta, ro_conn, set_meta
from .inventory_sync import full_sync

bp = Blueprint('admin', __name__, template_folder='templates/admin')

ADMIN_SECRET = os.environ.get('ADMIN_SECRET')
def _check_secret():
    if ADMIN_SECRET and request.headers.get('X-Admin-Secret') != ADMIN_SECRET:
        abort(403)


@bp.before_request
def before():
    _check_secret()


@bp.route('/inventory')
def inventory_page():
    last = get_meta('inventory_last_synced_at', 'never')
    count = get_meta('inventory_last_synced_count', '0')
    return render_template('admin/inventory.html', last=last, count=count, secret=ADMIN_SECRET or '')


@bp.route('/inventory/sync', methods=['POST'])
def inventory_sync():
    if get_meta('inventory_sync_running') == '1':
        return jsonify(started=False), 409

    set_meta('inventory_sync_running', '1')

    app = current_app._get_current_object()

    def runner():
        with app.app_context():
            full_sync()

    threading.Thread(target=runner).start()
    return jsonify(started=True)


@bp.route('/inventory/status')
def inventory_status():
    return jsonify(
        running=get_meta('inventory_sync_running', '0'),
        last_synced_at=get_meta('inventory_last_synced_at'),
        last_synced_count=get_meta('inventory_last_synced_count'),
        last_error=get_meta('inventory_last_error'),
        state=get_meta('inventory_sync_status', 'idle'),
    )


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
