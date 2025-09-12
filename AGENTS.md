# Agents Guide

This file teaches coding agents (Copilot/Codex/etc.) how to work safely and productively in this project.

## Mission
This app bundles/quotes products and integrates with the **RepairShopr** API for data export/sync. It’s a Flask app with a single SQL database.

## Repo Map (high level)
- `app/` — Flask application (factory pattern recommended), models, routes, CLI.
- `static/` — Static assets for the UI.
- `tests/` — Unit/integration tests.
- `run.py` — App entrypoint for `flask run` / gunicorn.
- `docs/repairshopr/` — **Vendored API spec** (OpenAPI/Swagger) for RepairShopr.
- `docs/agents/` — Agent playbooks (this doc, API-specific guides).

> The README mentions a data-export CLI: `flask rs-export full` (see “RepairShopr Export” section). Prefer using/expanding that CLI rather than duplicating logic. 
> _Source: repository README preview._ 

## Environment & Secrets
Never hardcode secrets or base URLs. Read from env vars:
- `DATABASE_URL` — SQLAlchemy URI (dev default may be SQLite under `instance/`).
- `SECRET_KEY` — Flask secret.
- `REPAIRSHOPR_API_KEY` — API token.
- `REPAIRSHOPR_SUBDOMAIN` — e.g. `yourco` for `https://yourco.repairshopr.com`.
- `EXPORT_DIR` — for exporter outputs (defaults to `./exports`).
- `REPAIRSHOPR_EXPORT_TO_DB` — `"true"` to upsert exports into the DB.

Create `.env.example` with **placeholders only**. Do not commit real keys.

## Coding Rules (important)
- **One database only.** Import the shared `db` object everywhere; do not create ad-hoc engines or use `sqlite3.connect`.
- Use Flask app factory patterns. Avoid `create_all()` in request paths; handle schema via **migrations**.
- When calling RepairShopr: prefer a **single integration layer** (client/wrapper) with retries, timeouts, and backoff on HTTP 429.
- Sanitize/escape all template output; do not pipe untrusted strings through `|safe`.
- Write tests for new modules and any bug fixes.
- Keep PRs small and focused.

## Task Playbooks
- **RepairShopr API work:** Read `docs/agents/repairshopr.md`. It explains how to use `docs/repairshopr/openapi.yaml`, generate typed clients, handle pagination, and respect rate limits.
- **Exporter:** If adding new datasets, extend the existing CLI (`flask rs-export ...`) and reuse the same request/caching/backoff utilities.
- **DB changes:** create a migration and update models; never bypass the shared SQLAlchemy instance.

## Don’t Do This
- Don’t commit secrets or real tokens.
- Don’t spin up a second DB or put raw SQL files under version control.
- Don’t call the RepairShopr API directly from templates or random modules; go through the integration layer.

## Local Dev (quick start)
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=run.py
flask run
