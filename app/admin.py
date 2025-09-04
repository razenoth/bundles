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

from .inventory_store import get_sync_state, set_sync_state, ro_conn
from .inventory_sync import full_sync, quick_update, utcnow_iso

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
    st = get_sync_state()
    return render_template(
        'admin/inventory.html',
        last_full=st.get('last_full_sync_at', 'never'),
        last_quick=st.get('last_quick_check_at', 'never'),
        max_id=st.get('max_product_id_seen', 0),
        secret=ADMIN_SECRET or '',
    )


def _start_background(target):
    app = current_app._get_current_object()

    def runner():
        with app.app_context():
            try:
                result = target()
                set_sync_state(
                    {
                        'inventory_sync_running': 0,
                        'last_error': None,
                        'last_job_result': json.dumps(result),
                    }
                )
            except Exception as e:  # pragma: no cover
                set_sync_state(
                    {
                        'inventory_sync_running': 0,
                        'last_error': f"{utcnow_iso()} {type(e).__name__}: {e}",
                    }
                )
    threading.Thread(target=runner, daemon=False).start()


@bp.route('/inventory/quick', methods=['POST'])
def inventory_quick():
    st = get_sync_state()
    if st.get('inventory_sync_running'):
        return jsonify(started=False), 409
    set_sync_state({'inventory_sync_running': 1})
    _start_background(quick_update)
    return jsonify(started=True)


@bp.route('/inventory/full', methods=['POST'])
def inventory_full():
    st = get_sync_state()
    if st.get('inventory_sync_running'):
        return jsonify(started=False), 409
    set_sync_state({'inventory_sync_running': 1})
    _start_background(full_sync)
    return jsonify(started=True)


@bp.route('/inventory/status')
def inventory_status():
    st = get_sync_state()
    result = st.get('last_job_result')
    return jsonify(
        running=st.get('inventory_sync_running', 0),
        last_full_sync_at=st.get('last_full_sync_at'),
        last_quick_check_at=st.get('last_quick_check_at'),
        next_audit_page=st.get('next_audit_page'),
        max_product_id_seen=st.get('max_product_id_seen'),
        last_error=st.get('last_error'),
        last_job_result=json.loads(result) if result else None,
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
