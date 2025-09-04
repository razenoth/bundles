"""Inventory synchronisation helpers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict

from .inventory_store import (
    upsert_products,
    get_sync_state,
    set_sync_state,
    compute_local_checksum,
)
from .repairshopr_client import fetch_products_page

PAGE_SIZE = 25


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def full_sync(sort: str = "id ASC") -> Dict[str, int]:
    """Perform a full inventory pull."""
    page = 1
    total = 0
    last_page_items = []
    while True:
        items = fetch_products_page(page=page, sort=sort)
        logging.info("full_sync page=%s items=%s", page, len(items))
        if not items:
            break
        upsert_products(items)
        total += len(items)
        last_page_items = items
        if len(items) < PAGE_SIZE:
            break
        page += 1

    st = get_sync_state()
    st["last_full_sync_at"] = utcnow_iso()
    if total and last_page_items:
        st["max_product_id_seen"] = max(
            st.get("max_product_id_seen") or 0, max(p["id"] for p in last_page_items)
        )
    set_sync_state(st)
    logging.info("full_sync completed pages=%s total=%s", page, total)
    return {"pages": page, "total": total}


def quick_update(k_pages: int = 5) -> Dict[str, int]:
    """Fast delta sync pulling new products and auditing existing ones."""
    st = get_sync_state()
    max_known = st.get("max_product_id_seen") or 0

    # --- A) New products
    new_total = 0
    page = 1
    new_items: list = []
    while True:
        items = fetch_products_page(page=page, sort="id DESC")
        logging.info("quick_update new page=%s items=%s", page, len(items))
        if not items:
            break
        min_id = min(p["id"] for p in items)
        new_items = [p for p in items if p["id"] > max_known]
        if new_items:
            upsert_products(new_items)
            new_total += len(new_items)
        if min_id <= max_known or len(items) < PAGE_SIZE:
            break
        page += 1
    if new_total and new_items:
        st["max_product_id_seen"] = max(max_known, max(p["id"] for p in new_items))

    # --- B) Rolling audit
    updated, checked = 0, 0
    cursor = max(1, st.get("next_audit_page") or 1)
    local_page = cursor
    pages_done = 0
    while pages_done < k_pages:
        items = fetch_products_page(page=local_page, sort="id ASC")
        logging.info("quick_update audit page=%s items=%s", local_page, len(items))
        if not items:
            break
        for p in items:
            existing = compute_local_checksum(p)
            if existing != p.get("_local_checksum"):
                upsert_products([p])
                updated += 1
            checked += 1
        pages_done += 1
        if len(items) < PAGE_SIZE:
            local_page = 1
        else:
            local_page += 1

    st["next_audit_page"] = local_page
    st["last_quick_check_at"] = utcnow_iso()
    set_sync_state(st)
    logging.info(
        "quick_update completed new=%s updated=%s checked=%s next_page=%s",
        new_total,
        updated,
        checked,
        local_page,
    )
    return {"new": new_total, "updated": updated, "checked": checked, "next_audit_page": local_page}


