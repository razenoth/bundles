
---

# `docs/agents/repairshopr.md`

```markdown
# Agents Playbook: RepairShopr Integration

This guide teaches an agent how to navigate and use the RepairShopr API *in this repo*.

## Where the API spec lives
- **Primary spec:** `docs/repairshopr/openapi.yaml` (OpenAPI 3 YAML).
- **Upstream source (public):** https://api-docs.repairshopr.com/swagger.json (mirrored locally).

Always consult the local `openapi.yaml` first so codegen and types are stable even if upstream changes. (There may also be a `swagger.json` mirror for reference.)

## Authentication & Base URL
- Base URL: `https://<REPAIRSHOPR_SUBDOMAIN>.repairshopr.com/api/v1`
- Auth: API key from env (`REPAIRSHOPR_API_KEY`), typically passed as a header or query param per the spec.
- Never hardcode tokens.

## How to generate a typed Python client (preferred)
If a generated client already exists under `clients/repairshopr_py/`, **use it**. Otherwise generate:

```bash
pip install openapi-python-client
openapi-python-client generate \
  --path docs/repairshopr/openapi.yaml \
  --output clients/repairshopr_py \
  --meta none
