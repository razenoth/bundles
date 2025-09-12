Bundles — Quoting & Estimates Tool (Flask)

SUMMARY
-------
Bundles is a Flask web app for building product bundles, creating estimates, and syncing/searching data with RepairShopr. It uses a single SQL database via SQLAlchemy and exposes a CLI to export/ingest RepairShopr data for offline use.

KEY FEATURES
------------
• Create and manage Bundles and Estimates.
• Search/add products (local DB cache + external RepairShopr).
• Export data from RepairShopr via a resumable CLI.
• Single database for the entire app (SQLAlchemy + Flask-Migrate).
• “Agents” guides to help AI tooling follow the project conventions.
• Vendored OpenAPI (OAS3) spec for RepairShopr to support typed client code.

REPO LAYOUT
-----------
app/                 Flask application (blueprints, models, views, CLI)
static/              Front-end assets
tests/               Unit/integration tests
run.py               App entrypoint for flask/gunicorn
Makefile             Optional developer helpers
docs/repairshopr/    OpenAPI spec (openapi.yaml) mirrored from RepairShopr
AGENTS.md            Top-level agent instructions (if present)
docs/agents/         API-focused agent playbooks (if present)

PREREQUISITES
-------------
• Python 3.10+ recommended
• SQLite (default) or any SQLAlchemy-supported DB (Postgres/MySQL/etc.)
• RepairShopr API key and subdomain (if using the integration)
• Node or Docker only if you plan to re-convert vendor specs (optional)

QUICK START (DEV)
-----------------
1) Create and activate a virtual environment, then install:
   python -m venv venv
   source venv/bin/activate         (Windows: venv\Scripts\activate)
   pip install -r requirements.txt

2) Configure environment variables (examples):
   export FLASK_APP=run.py
   export DATABASE_URL="sqlite:///instance/app.db"
   export SECRET_KEY="change-me"
   export REPAIRSHOPR_SUBDOMAIN="your-subdomain"
   export REPAIRSHOPR_API_KEY="your-api-key"
   # optional for exporter:
   export EXPORT_DIR="./exports"
   export REPAIRSHOPR_EXPORT_TO_DB="true"

3) Initialize database (make sure ./instance exists):
   mkdir -p instance
   flask db upgrade

4) Run the app:
   flask run
   # Visit http://127.0.0.1:5000

ENVIRONMENT VARIABLES
---------------------
DATABASE_URL                SQLAlchemy URI. Dev default is sqlite:///instance/app.db
SECRET_KEY                  Flask secret; set a strong value in production
FLASK_ENV                   "development" or "production"
REPAIRSHOPR_SUBDOMAIN       <yourco> for https://<yourco>.repairshopr.com
REPAIRSHOPR_API_KEY         API token (do not commit)
EXPORT_DIR                  Where exporter writes newline-delimited JSON (default ./exports)
REPAIRSHOPR_EXPORT_TO_DB    "true" to upsert exported data into the DB (optional)

DATABASE & MIGRATIONS
---------------------
• Schema changes must use Flask-Migrate (Alembic).
• Typical flow:
  export FLASK_APP=run.py
  flask db migrate -m "describe change"
  flask db upgrade

REPAIRSHOPR INTEGRATION
-----------------------
• The local vendored spec is in docs/repairshopr/openapi.yaml.
• Prefer generating a typed client and using a single integration module
  that adds timeouts, retries, and 429 backoff.
• Keep all outbound calls in one place (no ad-hoc requests across the app).

EXPORTER CLI (RepairShopr)
--------------------------
Full export:
  flask rs-export full

Notes:
• Results are newline-delimited JSON under EXPORT_DIR (default ./exports).
• A checkpoint file tracks progress so reruns resume where they left off.
• Tickets/invoices support incremental sync using since_updated_at.
• Set REPAIRSHOPR_EXPORT_TO_DB="true" to upsert into the app’s DB.

SECURITY NOTES
--------------
• Never commit secrets or real tokens; use environment variables (.env for local only).
• CSRF protection and secure headers should be enabled for forms/routes.
• In production: disable DEBUG, serve behind TLS, and set SESSION_COOKIE_SECURE=True.

TESTING
-------
• Activate venv and run:
  pytest

DEPLOYMENT (BASIC)
------------------
gunicorn --bind 0.0.0.0:8000 "run:app"

Typical systemd unit (example):
  [Unit]
  Description=Bundles (Flask)
  After=network.target

  [Service]
  User=www-data
  WorkingDirectory=/srv/bundles
  EnvironmentFile=/etc/bundles.env
  ExecStart=/srv/bundles/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:8000 run:app
  Restart=always

  [Install]
  WantedBy=multi-user.target

AGENTS
------
• Read AGENTS.md for repo-wide guidance.
• For API tasks, see docs/agents/repairshopr.md.
• Use the local OpenAPI file and any generated client—avoid hand-rolled requests.

LICENSE
-------
Proprietary/internal (update if you choose a license later).

CONTACT
-------
Maintainer: Andrew Willis
