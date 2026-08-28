# okapi-api

The FastAPI service. Implements the three layers from the architecture doc:

| Layer | Lives in | Responsibility |
|-------|----------|----------------|
| 3 — AI Action | `services/` (`rag_service`, `form_fill_service`, `extraction_service`) | RAG retrieval, gated auto-fill, LLM drafting — only reachable once Layer 2 clears |
| 2 — Verification & Compliance Gate | `gate/` | RBAC+ABAC via OPA, compliance evaluation, Merkle integrity check — the only caller of Layer 1 |
| 1 — Trusted Data Core | `repositories/`, `models/`, `services/` (`versioning_`, `lineage_`, `integrity_`, `propagation_`) | field-level version history, hash-chained lineage DAG, PostgreSQL storage |

## Layout

```
src/okapi_api/
  main.py         app instantiation + router registration (HTTP only, ~5 lines/route)
  core/           config (pydantic-settings), security (JWT), logging
  api/v1/         routers — parse request, call one service, return
  services/       orchestration + domain logic (unit-tested with mocked repo/gate)
  gate/           Gate.check entrypoint + OPA HTTP client
  repositories/   all SQLAlchemy queries — nothing else touches a Session
  models/         SQLAlchemy ORM models
  schemas/        Pydantic request/response bodies
  db/             engine/session factory + Alembic migrations
```

## Local dev

From the repo root:

```
uv sync
uv run --package okapi-api uvicorn okapi_api.main:app --reload
uv run --package okapi-api alembic -c apps/api/alembic.ini upgrade head
```
