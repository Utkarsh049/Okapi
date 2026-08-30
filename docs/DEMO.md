# Okapi — 50% Review Demo

Everything below runs through the API (`/docs`, curl, or `scripts/demo.py`). No UI.

## Setup

```bash
uv sync
cp .env.example .env          # then set OKAPI_DATABASE_URL to your Postgres
                              # and OKAPI_OPA_URL (default http://localhost:8000 -> 8181)

# schema + demo data
uv run --package okapi-api alembic -c apps/api/alembic.ini upgrade head
uv run --package okapi-api python scripts/seed.py

# OPA (single binary, no Docker): serve the policy bundle
.tools/opa.exe run --server --addr localhost:8181 packages/policies

# API
uv run --package okapi-api uvicorn okapi_api.main:app --port 8000
```

Then either open <http://localhost:8000/docs> or:

```bash
uv run --package okapi-api python scripts/demo.py
```

## What the demo shows (the patent-relevant mechanisms)

| # | Step | Mechanism (architecture doc) |
|---|------|------------------------------|
| 1 | Issue JWTs for a human clinician and an AI service account | AI-vs-human actor identity (§6, mechanism 4.6) |
| 2 | Create a document, register 3 fields (one PHI, needs sign-off) | Field is the atomic unit, not the document (§1.2, §4.1) |
| 3 | `PATCH` a field twice | Field-level version history — `field_versions` with `value_hash` + parent array (§4.1) |
| 4 | Reconcile two edits into one | Merge node: `parent_version_id` has two entries → DAG, not a list (§4.2, mechanism 4.4) |
| 5 | `GET …/lineage` | Hash-chained Merkle DAG — `edge_hash = SHA256(parent_id + parent.value_hash + child.value_hash)` (§4.2) |
| 6 | Query as a researcher | The Gate filters to `allowed_fields`; response omits what RBAC/ABAC deny (§5.1) |
| 7 | Query as the AI agent | `compliance/hipaa.rego` denies AI reads of PHI unless `acting_on_behalf_of` — pluggable regime (§6.1) |
| 8 | `UPDATE` a value directly in Postgres, re-check integrity | Independent hash recomputation catches an out-of-band edit (§4.2) |
| 9 | `GET /audit?document_id=…` | Append-only audit log, one row per field considered, human vs `ai_agent` (§4.1) |
| 10 | Edit `rbac.rego`, restart OPA, re-run step 6 | Policy-as-code: behaviour changes with no app change (§6, §6.1) |

## Implemented for this review

- **Trusted Data Core** — Postgres schema (8 tables), field-level versioning, hash-chained
  lineage DAG with branching/merge, recursive-CTE ancestor traversal, cross-document
  reference model + staleness propagation, append-only audit log.
- **Verification & Compliance Gate** — called before every repository read/write; RBAC +
  ABAC + one real compliance regime in OPA/Rego; returns `{allow, allowed_fields, reason}`;
  writes an audit row per decision; a denied write never touches the repository.
- **AI Action Layer** — field-scoped retrieval that can only draw on gate-approved fields;
  AI vs human distinguished on every decision and audit entry.
- **Platform** — uv monorepo, sync SQLAlchemy + Alembic, JWT auth (`/auth/token`),
  `mypy --strict`, ruff/black, `opa test`, CI, `docker-compose` for the full stack.

## Deliberately deferred (stated up front)

| Area | Now | Later |
|------|-----|-------|
| LLM key-data extraction | value supplied directly on field registration | `ExtractionService` + model call |
| RAG | `RAGService` returns permitted field values + a canned summary | pgvector embeddings + similarity search |
| Forms | — | `/forms/{id}/autofill` + `/submit` |
| Integrity root | independent per-edge / per-value hash recomputation | stored Merkle root column recomputed on write |
| Auth | access token only | refresh tokens, IdP, TLS termination |
| Scale (§11) | single Postgres, synchronous propagation | Neo4j lineage, async fan-out, multi-tenant gateway |
