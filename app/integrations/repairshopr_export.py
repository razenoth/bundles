import json
import logging
import os
import random
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, Optional, Tuple

import click
import requests
from flask import current_app

from app import db

# Configuration
MAX_RPM = int(os.getenv("MAX_RPM", "120"))
EXPORT_DIR = os.getenv("EXPORT_DIR", "./exports")
SUBDOMAIN = os.getenv("REPAIRSHOPR_SUBDOMAIN", "")
API_KEY = os.getenv("REPAIRSHOPR_API_KEY", "")
BASE_URL = f"https://{SUBDOMAIN}.repairshopr.com/api/v1"


class TokenBucket:
    """Simple token bucket limiter shared across the process."""

    def __init__(self, capacity: int = MAX_RPM, refill_per_min: int = MAX_RPM) -> None:
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_per_min / 60.0
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(
                    self.capacity,
                    self.tokens + (now - self.last) * self.refill_rate,
                )
                self.last = now
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                needed = (tokens - self.tokens) / self.refill_rate
            time.sleep(max(needed, 0.01))


bucket = TokenBucket()


class RepairShoprClient:
    def __init__(self, base_url: str = BASE_URL, api_key: str = API_KEY, timeout: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        )
        self.req_times: deque[float] = deque()

    def _record_request(self) -> None:
        now = time.monotonic()
        self.req_times.append(now)
        while self.req_times and self.req_times[0] < now - 60:
            self.req_times.popleft()

    def current_rpm(self) -> float:
        self._record_request()  # prune old
        return float(len(self.req_times))

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, tokens: int = 1) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        tries = 0
        while True:
            bucket.acquire(tokens)
            try:
                r = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as e:  # network issue
                tries += 1
                if tries > 3:
                    raise
                delay = min(2 ** tries, 30) + random.random()
                time.sleep(delay)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                tries += 1
                if tries > 3:
                    r.raise_for_status()
                delay = min(2 ** tries, 30) + random.random()
                time.sleep(delay)
                continue
            r.raise_for_status()
            self._record_request()
            return r.json()

    def paginate(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        start_page: int = 1,
        tokens: int = 1,
    ) -> Generator[Tuple[int, Iterable[Dict[str, Any]]], None, None]:
        page = start_page
        while True:
            q = dict(params or {})
            q["page"] = page
            data = self.get(path, params=q, tokens=tokens)
            payload: Iterable[Dict[str, Any]] = []
            for v in data.values():
                if isinstance(v, list):
                    payload = v
                    break
            if not payload:
                break
            yield page, payload
            meta = data.get("meta") or {}
            total_pages = meta.get("total_pages")
            if total_pages and page >= total_pages:
                break
            page += 1


class CheckpointStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        if path.exists():
            self.data = json.loads(path.read_text())
        else:
            self.data = {}

    def get(self, stream: str) -> Dict[str, Any]:
        return self.data.get(stream, {})

    def save(self, stream: str, page: int, cursor: Optional[str] = None) -> None:
        self.data[stream] = {"page": page}
        if cursor is not None:
            self.data[stream]["cursor"] = cursor
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2))


# Mapping stream -> (path, params, cursor_field)
STREAMS = [
    ("customers", "/customers", {}, None),
    ("contacts", "/contacts", {}, None),
    ("vendors", "/vendors", {}, None),
    ("products", "/products", {}, None),
    ("leads", "/leads", {}, None),
    ("tickets", "/tickets", {}, "updated_at"),
    ("invoices", "/invoices", {}, "updated_at"),
    ("estimates", "/estimates", {}, None),
    ("payments", "/payments", {}, None),
    ("purchase_orders", "/purchase_orders", {}, None),
    ("portal_users", "/portal_users", {}, None),
    ("customer_assets", "/customer_assets", {}, None),
    ("appointments", "/appointments", {}, None),
    ("canned_responses", "/canned_responses", {}, None),
    ("contracts", "/contracts", {}, None),
    ("schedules", "/schedules", {}, None),
    ("rmm_alerts", "/rmm_alerts", {}, None),
    ("wiki_pages", "/wiki_pages", {}, None),
]


def _upsert(model_cls, payload: Dict[str, Any]) -> None:
    if model_cls is None:
        return
    obj = model_cls.query.get(payload["id"]) if payload.get("id") else None
    if not obj:
        obj = model_cls(id=payload["id"])
    for col in model_cls.__table__.columns.keys():
        if col == "id":
            continue
        if col in payload:
            setattr(obj, col, payload[col])
    db.session.merge(obj)
    db.session.commit()


MODEL_MAP = {}


def _register_models():
    from app import models as m

    MODEL_MAP.update(
        {
            "products": getattr(m, "RSProduct", None),
            "customers": getattr(m, "RSCustomer", None),
            "vendors": getattr(m, "RSVendor", None),
            "invoices": getattr(m, "RSInvoice", None),
            "estimates": getattr(m, "RSEstimate", None),
            "line_items_invoices": getattr(m, "RSLineItem", None),
            "line_items_estimates": getattr(m, "RSLineItem", None),
            "purchase_orders": getattr(m, "RSPurchaseOrder", None),
        }
    )


def export_stream(
    client: RepairShoprClient,
    name: str,
    path: str,
    params: Optional[Dict[str, Any]],
    cursor_field: Optional[str],
    cp: CheckpointStore,
    export_to_db: bool,
) -> Tuple[int, Optional[str], list[int]]:
    start = cp.get(name)
    page = start.get("page", 0) + 1
    cursor = start.get("cursor")
    if cursor and cursor_field:
        params = dict(params or {})
        params["since_updated_at"] = cursor
    out = Path(EXPORT_DIR) / f"{name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    seen_ids: list[int] = []
    cursor_val: Optional[str] = cursor
    with open(out, "a", encoding="utf-8") as fh:
        for pg, items in client.paginate(path, params=params, start_page=page):
            for item in items:
                fh.write(json.dumps(item) + "\n")
                total += 1
                if export_to_db:
                    _upsert(MODEL_MAP.get(name), item)
                if name == "products" and item.get("id"):
                    seen_ids.append(int(item["id"]))
                if cursor_field and item.get(cursor_field):
                    val = item[cursor_field]
                    if not cursor_val or val > cursor_val:
                        cursor_val = val
            cp.save(name, pg, cursor_val)
            logging.info(
                "%s page=%s total=%s rpm=%.1f", name, pg, total, client.current_rpm()
            )
    return total, cursor_val, seen_ids


def export_line_items(client: RepairShoprClient, cp: CheckpointStore, export_to_db: bool) -> None:
    for key, param in (
        ("line_items_invoices", {"invoice_id_not_null": "true"}),
        ("line_items_estimates", {"estimate_id_not_null": "true"}),
    ):
        export_stream(client, key, "/line_items", param, None, cp, export_to_db)


def export_product_serials(
    client: RepairShoprClient,
    product_ids: Iterable[int],
    cp: CheckpointStore,
) -> None:
    state = cp.get("product_serials")
    start_index = state.get("product_index", 0)
    page = state.get("page", 0) + 1
    ids = list(product_ids)
    out = Path(EXPORT_DIR) / "product_serials.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as fh:
        for idx in range(start_index, len(ids)):
            pid = ids[idx]
            pg = page
            while True:
                data = client.get(
                    f"/products/{pid}/product_serials",
                    params={"page": pg},
                    tokens=2,
                )
                items = data.get("product_serials") or data.get("data") or []
                if not items:
                    break
                for item in items:
                    item["product_id"] = pid
                    fh.write(json.dumps(item) + "\n")
                cp.save("product_serials", idx, str(pg))
                logging.info(
                    "product_serials product=%s page=%s rpm=%.1f", pid, pg, client.current_rpm()
                )
                pg += 1
            page = 1
    cp.save("product_serials", len(ids), "")


@click.group("rs-export")
def rs_export_cli() -> None:
    """RepairShopr export commands."""


@rs_export_cli.command("full")
@click.option("--include-serials", is_flag=True, help="Include product serials")
def full_command(include_serials: bool) -> None:
    full_export(include_serials=include_serials)


def full_export(include_serials: bool = False) -> None:
    logging.basicConfig(level=logging.INFO)
    _register_models()
    client = RepairShoprClient()
    export_to_db = os.getenv("REPAIRSHOPR_EXPORT_TO_DB", "false").lower() == "true"
    cp = CheckpointStore(Path(EXPORT_DIR) / "checkpoint.json")
    all_product_ids: list[int] = []
    for name, path, params, cursor_field in STREAMS:
        _, _, ids = export_stream(
            client, name, path, params, cursor_field, cp, export_to_db
        )
        if name == "products":
            all_product_ids = ids
    export_line_items(client, cp, export_to_db)
    if include_serials and all_product_ids:
        export_product_serials(client, all_product_ids, cp)
