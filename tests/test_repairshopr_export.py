import os
import time

from app.integrations import repairshopr_export as rs


os.environ.setdefault("REPAIRSHOPR_SUBDOMAIN", "test")
os.environ.setdefault("REPAIRSHOPR_API_KEY", "key")


def test_paginate_stops(monkeypatch):
    client = rs.RepairShoprClient()
    responses = [
        {"customers": [{"id": 1}], "meta": {"total_pages": 2}},
        {"customers": [{"id": 2}], "meta": {"total_pages": 2}},
    ]

    def fake_get(path, params=None, tokens=1):
        page = params["page"]
        if page <= len(responses):
            return responses[page - 1]
        return {"customers": []}

    monkeypatch.setattr(client, "get", fake_get)
    pages = list(client.paginate("/customers"))
    assert len(pages) == 2
    assert pages[0][0] == 1 and pages[1][0] == 2


def test_limiter_behaviour():
    bucket = rs.TokenBucket(capacity=2, refill_per_min=120)
    start = time.monotonic()
    bucket.acquire()
    bucket.acquire()
    bucket.acquire()
    assert time.monotonic() - start >= 0.5


class DummyResponse:
    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self._data = data or {"ok": True}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(self.status_code)


def test_backoff_on_429(monkeypatch):
    client = rs.RepairShoprClient()
    calls = []
    seq = [DummyResponse(429), DummyResponse(500), DummyResponse(200)]

    def fake_get(url, params=None, timeout=None):
        resp = seq[len(calls)]
        calls.append(1)
        return resp

    sleeps = []
    monkeypatch.setattr(rs, "bucket", type("B", (), {"acquire": lambda self, n=1: None})())
    monkeypatch.setattr(client.session, "get", fake_get)
    monkeypatch.setattr(rs.time, "sleep", lambda s: sleeps.append(s))
    data = client.get("/x")
    assert data["ok"] is True
    assert len(calls) == 3
    assert len(sleeps) == 2
    assert sleeps[1] > sleeps[0]


def test_checkpoint_resume(tmp_path, monkeypatch):
    cp = rs.CheckpointStore(tmp_path / "ck.json")
    cp.save("stream", 1)
    client = rs.RepairShoprClient()

    def fake_paginate(path, params=None, start_page=1, tokens=1):
        assert start_page == 2
        yield start_page, [{"id": 2}]

    monkeypatch.setattr(client, "paginate", fake_paginate)
    rs.export_stream(client, "stream", "/s", {}, None, cp, False)
    assert cp.get("stream")["page"] == 2


def test_line_items_queries(monkeypatch, tmp_path):
    client = rs.RepairShoprClient()
    cp = rs.CheckpointStore(tmp_path / "ck.json")
    calls = []

    def fake_export_stream(client, name, path, params, cursor_field, cp, export_to_db):
        calls.append((name, params))
        return 0, None, []

    monkeypatch.setattr(rs, "export_stream", fake_export_stream)
    rs.export_line_items(client, cp, False)
    assert ("line_items_invoices", {"invoice_id_not_null": "true"}) in calls
    assert ("line_items_estimates", {"estimate_id_not_null": "true"}) in calls
