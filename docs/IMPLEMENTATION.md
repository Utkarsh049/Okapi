# Okapi — Implementation Reference

Everything built so far, every API endpoint, and what each file does. Section numbers
in parentheses point at `architecture_okapi.pdf`. For the demo walkthrough see
[DEMO.md](DEMO.md); for the directory map see [../STRUCTURE.md](../STRUCTURE.md).

---

## 1. Status

| Milestone | Contents | State |
|-----------|----------|-------|
| Scaffold | uv monorepo, FastAPI skeleton, empty Rego, docker-compose, CI | done, pushed |
| 1 — Data layer | 8 ORM models, `0001_core_schema` migration, 4 repositories, `seed.py`, sync `session.py` | code done |
| 2 — Auth + Gate + write | `/auth/token`, `deps.py` DI, `Gate`, `OpaPolicyClient`/`StubPolicyClient`, versioning/lineage/propagation/edit services, real `rbac`/`abac`/`hipaa`/`authz` Rego | code done |
| 3 — Read + integrity + demo | RAG stub, retrieval service, integrity verify, `/query` `/lineage` `/integrity` `/audit` `/signoff`, `demo.py`, `DEMO.md` | code done |

**Verified:** `ruff`, `black`, `mypy --strict` (54 files), `pytest` (12 unit), `opa test` (5/5).
**Not yet run:** anything needing Postgres — `alembic upgrade head`, `seed.py`, the recursive
CTE, the full HTTP flow, real OPA. 4 integration tests skip until a database is configured.

Branch: `feat/core-impl` (commits `ade52a7`, `3fd4427`, `99f2096`).

---

## 2. How a request flows

```
HTTP request
  -> router (apps/api/src/okapi_api/api/v1/*.py)      parse, 404 checks, call ONE service
     -> service (services/*.py)                       orchestration
        -> Gate.check_* (gate/gate.py)                BEFORE any repo read/write
           -> PolicyClient.evaluate (gate/policy_client.py) -> OPA sidecar (packages/policies/*.rego)
           -> AuditRepository.record                  one audit_log row per decision
        -> repositories/*.py                          the only place SQL runs
           -> models/*.py + db/session.py             SQLAlchemy -> Postgres
```

- A **denied write** raises `GateDenied` inside the Gate; the repository is never reached.
  `main.py` maps it to HTTP 403 (the deny row is already written).
- A **read** calls `Gate.check_fields`, which returns only the permitted field keys; the
  response is built from those alone.
- The LLM is not on any path yet — extraction and RAG are stubbed (`services/*_service.py`).

---

## 3. API reference

Base path `/api/v1` (constant `API_V1_PREFIX`). All endpoints except `/health` and
`/auth/token` require `Authorization: Bearer <jwt>`. Interactive docs at `/docs`.

### `GET /health`
No auth. `200 -> {"status": "ok"}`.

### `POST /api/v1/auth/token`
No auth. Body is an OAuth2 **form** (`application/x-www-form-urlencoded`): `username`
(= user email), `password`.
`200 -> {"access_token": "<jwt>", "token_type": "bearer"}` · `401` on bad credentials.
JWT claims: `sub` (user id), `role`, `actor_type` (`human`|`ai_agent`, derived from role),
`attributes` (department/clearance_level/…), `iat`, `exp` (TTL `OKAPI_ACCESS_TOKEN_TTL_SECONDS`, default 900s).

### `POST /api/v1/documents`
Body `DocumentCreate` `{title, doc_type}` -> `201` `DocumentRead`
`{id, title, doc_type, created_by, created_at}`. `created_by` is taken from the token.

### `POST /api/v1/documents/{document_id}/fields`
Body `FieldRegister` `{field_key, field_type="text", requires_signoff=false, category=null, value=null}`.
Registers a field; if `value` is given, creates version 1 (extraction from raw text is deferred).
`201` `FieldRead` `{id, document_id, field_key, field_type, requires_signoff, category}` · `404` if document missing.

### `PATCH /api/v1/documents/{document_id}/fields/{field_id}`  — **gated write**
Body `FieldPatch` `{new_value, amendment_note=null, parent_version_ids=null, is_ai_generated=false}`.
Flow (`EditService.apply_edit`): `Gate.check_write` → `VersioningService.create_version`
(content hash, parent = current head unless `parent_version_ids` given — **two ids = a merge node**)
→ `LineageService.link` (writes `lineage_edges` with `edge_hash`) → `PropagationService.flag_dependents`.
`200` `VersionRead` `{id, field_id, value, value_hash, parent_version_id[], created_by, created_at, is_ai_generated, amendment_note, status}` ·
`403 {"detail": reason}` if the Gate denies (deny already in `audit_log`) · `404` if document/field missing.

### `POST /api/v1/documents/{document_id}/query`  — **field-scoped read**
Body `QueryRequest` `{question}` (defaults to a summary prompt).
Flow (`RetrievalService.query`): `Gate.check_fields` over every field on the document
(one audit row each) → `RAGService.retrieve` over only the allowed keys.
`200` `QueryResponse` `{answer, fields: {key: value}, allowed_fields: [...], withheld_fields: [...]}` · `404` if document missing.
`answer` is a stub string (no embeddings/LLM).

### `GET /api/v1/documents/{document_id}/lineage`
`200` `LineageGraph` `{document_id, nodes: [{id, field_id, value_hash, status, is_ai_generated, parent_version_id[], created_at}], edges: [{child_version_id, parent_version_id, edge_hash}]}` · `404` if missing.

### `GET /api/v1/documents/{document_id}/integrity`
`200 -> {document_id, ok: bool, versions_checked, edges_checked, value_hash_mismatches: [...], edge_hash_mismatches: [...], merkle_root}`.
`IntegrityService.verify` recomputes every `value_hash` and `edge_hash`; any single-point
out-of-band edit (e.g. a direct `UPDATE`) makes `ok` false.

### `POST /api/v1/fields/{field_id}/signoff`
Human approval for a gated field: clears the head version's `pending_signoff` status and
writes an `audit_log` `signoff`/`allow` row. `200` `VersionRead` · `404`/`409`.

### `GET /api/v1/audit`
Query params (all optional): `actor_id`, `actor_type` (`human`|`ai_agent`), `document_id`,
`decision` (`allow`|`deny`), `limit` (default 200).
`200 -> [AuditRead {id, actor_id, actor_type, action, document_id, field_id, decision, reason, evaluated_at}]`, newest first.

### `POST /api/v1/forms/*`
Router registered, **no endpoints yet** — `autofill`/`submit` are deferred.

---

## 4. File-by-file

### `packages/shared/src/okapi_shared/` — cross-layer contracts (no I/O)

| File | What it does |
|------|--------------|
| `enums.py` | `ActorType(human, ai_agent)`, `Decision(allow, deny)`, `EdgeAction(read, write)`, `ReferenceStatus(current, stale)` — `StrEnum`, values mirror the DB enums. |
| `contracts.py` | `GateActor` (sub, role, actor_type, `attributes: dict[str, object]`, acting_on_behalf_of), `PolicyInput` (actor, action, field_key, document_metadata), `PolicyResult` (allow, allowed_fields, reason). Exact shapes exchanged with OPA. |
| `constants.py` | `API_V1_PREFIX="/api/v1"`, `HASH_ALGORITHM="sha256"`, `OPA_DECISION_PATH="okapi/authz/result"`. |
| `__init__.py` | Re-exports the public names. |

### `apps/api/src/okapi_api/core/` — infrastructure

| File | What it does |
|------|--------------|
| `config.py` | `Settings` (pydantic-settings, `OKAPI_` env prefix): `database_url`, `opa_url`, `jwt_secret`, `jwt_algorithm`, `access_token_ttl_seconds`, `anthropic_api_key`. `get_settings()` is `lru_cache`d. |
| `security.py` | `hash_password` / `verify_password` (bcrypt via passlib); `encode_access_token(claims)` / `decode_access_token(token)` (PyJWT, HS256). AuthN only — AuthZ is OPA's job. |
| `hashing.py` | `hash_value(str)` → content hash for `field_versions`; `hash_edge(parent_id, parent_hash, child_hash)` → `SHA256(parent_id + parent.value_hash + child.value_hash)` for `lineage_edges`. Pure library code, part of the deterministic core. |
| `logging.py` | `configure_logging()` — one JSON-line stdout handler. |
| `deps.py` | **DI hub.** `oauth2_scheme`; `DbSession`/`CurrentActor` annotated types; `get_current_actor` decodes the Bearer token into a `GateActor` (401 on failure); factory functions that assemble every repository, the `Gate` (policy client + audit repo), and each service. This is where constructor injection happens so everything stays mockable. |

### `apps/api/src/okapi_api/db/` — persistence

| File | What it does |
|------|--------------|
| `session.py` | Sync `create_engine` + `SessionFactory` (`sessionmaker`). `get_session()` FastAPI dependency: yields a `Session`, commits on success, rolls back on exception, always closes. The only place a session is created. |
| `migrations/env.py` | Alembic environment; pulls the URL from `get_settings()` (strips the `+psycopg` suffix) and metadata from `models.Base`. |
| `migrations/versions/0001_core_schema.py` | Hand-written first migration: 3 enum types + 8 tables + indexes/constraints, matching the ORM models exactly. `downgrade()` drops them in FK-safe order. |
| `migrations/script.py.mako` | Template for future generated migrations. |

### `apps/api/src/okapi_api/models/` — SQLAlchemy ORM (SQLAlchemy 2.0 typed `Mapped`)

| File | Table(s) | Notes |
|------|----------|-------|
| `base.py` | — | `Base(DeclarativeBase)`; `actor_type_enum`/`decision_enum`/`reference_status_enum` bound to the metadata once (so Alembic creates each PG enum a single time), `values_callable` so the *value* (`human`) is stored, not the name. |
| `user.py` | `users` | id, email (unique), full_name, role, `password_hash` (prototype convenience), `attributes` JSONB, created_at. `actor_type` is a computed property from `role`. |
| `document.py` | `documents` | id, title, doc_type, created_by→users, created_at. Container only — no versioned content. |
| `field.py` | `fields`, `field_versions` | `fields`: document_id, field_key, field_type, requires_signoff, `category` (tag ABAC/compliance key off), unique (document_id, field_key). `field_versions`: value, `value_hash`, **`parent_version_id: UUID[]`** (array → DAG, enables merge), created_by, is_ai_generated, amendment_note, `status` (active/pending_signoff/auto_approved). |
| `lineage.py` | `lineage_edges` | child_version_id, parent_version_id (both → field_versions), `edge_hash`; unique (child, parent). |
| `reference.py` | `field_references` | source_field_id, referencing_document_id, referencing_field_id, `status` (current/stale) — the cross-document dependency graph for propagation. |
| `compliance.py` | `compliance_rules` | rule_name, category, opa_package_path, active, version, updated_at — registry of which Rego regimes are on. |
| `audit.py` | `audit_log` | actor_id, `actor_type`, action, document_id?, field_id?, `decision`, reason, evaluated_at — append-only. |
| `__init__.py` | — | Imports every model so `Base.metadata` is complete for Alembic / `create_all`. |

### `apps/api/src/okapi_api/repositories/` — the only place SQL runs

| File | Key methods |
|------|-------------|
| `user_repository.py` | `get(id)`, `get_by_email(email)`. |
| `document_repository.py` | `create(title, doc_type, created_by)`, `get(id)`, `list_all()`. |
| `field_repository.py` | `register_field`, `get_field`, `get_field_by_key`, `get_fields_for_document`; `create_version`, `get_version`, `get_head_version` (most recent), `list_versions`, `set_version_status`; `add_lineage_edge`, `get_edges_for_document`, `get_versions_for_document`; **`ancestors(version_id)`** — recursive CTE (`WHERE fv.id = ANY(a.parent_version_id)`, `UNION` so a merge is visited once); `add_reference`, `references_to`, `mark_reference_stale`. |
| `audit_repository.py` | `record(...)` (append), `query(actor_id?, actor_type?, document_id?, decision?, limit)`. |

### `apps/api/src/okapi_api/gate/` — Layer 2, the choke point

| File | What it does |
|------|--------------|
| `policy_client.py` | `PolicyClient` `Protocol` (`evaluate(PolicyInput) -> PolicyResult`); `OpaPolicyClient` (sync `httpx` POST to `/v1/data/okapi/authz/result`, `{}`→deny); `StubPolicyClient` (allow-all except an explicit `{(field_key, action)}` denial set) for unit tests. |
| `gate.py` | `GateDenied` exception; `_doc_meta(document, field)` builds `document_metadata`; `Gate._decide` = evaluate + write one `audit_log` row; `Gate.check_write` (raises `GateDenied` on deny), `Gate.check_fields` (returns the allowed subset of field keys). |

### `apps/api/src/okapi_api/services/` — orchestration + domain logic

| File | What it does |
|------|--------------|
| `versioning_service.py` | `create_version(field_id, new_value, actor_id, parent_ids=None, …)` — default parent = head; `value_hash = hash_value(new_value)`; inserts via the repo. The field-level versioning mechanism. |
| `lineage_service.py` | `link(child_version, parent_ids)` — for each parent, `edge_hash = hash_edge(...)`, insert a `lineage_edges` row. Two parents ⇒ merge commit. |
| `propagation_service.py` | `flag_dependents(source_field_id)` — walk `field_references`, set each to `stale`, return count. |
| `edit_service.py` | `apply_edit(actor, document, field, new_value, …)` — `Gate.check_write` → `create_version` → `lineage.link` → `propagation.flag_dependents`. A write is an amendment, never an overwrite. |
| `retrieval_service.py` | `query(actor, document, question)` — `Gate.check_fields` over all fields → allowed keys → `RAGService.retrieve` → `{answer, fields, allowed_fields, withheld_fields}`. |
| `rag_service.py` | **STUB.** `retrieve(document_id, allowed_field_keys, question)` returns the head value of each permitted field + a canned summary. No embeddings, no LLM. |
| `integrity_service.py` | `verify(document_id)` recomputes every `value_hash` and `edge_hash`, returns mismatch lists + `ok`. `merkle_root(document_id)` folds sorted edge hashes. No stored root column (deferred) — catches every single-point tamper. |
| `extraction_service.py`, `form_fill_service.py` | Still docstring stubs — deferred (LLM). |

### `apps/api/src/okapi_api/api/v1/` — routers (HTTP only, thin)

| File | Endpoints |
|------|-----------|
| `auth.py` | `POST /auth/token`. |
| `documents.py` | `POST /documents`, `POST /{id}/fields`, `PATCH /{id}/fields/{field_id}`, `POST /{id}/query`, `GET /{id}/lineage`, `GET /{id}/integrity`. |
| `fields.py` | `POST /fields/{field_id}/signoff`. |
| `audit.py` | `GET /audit`. |
| `forms.py` | router only, no endpoints (deferred). |

### `apps/api/src/okapi_api/schemas/` — Pydantic request/response bodies

`document.py` (`DocumentCreate`, `DocumentRead`), `field.py` (`FieldRegister`, `FieldRead`,
`FieldPatch`, `VersionRead`), `read.py` (`QueryRequest`, `QueryResponse`), `lineage.py`
(`LineageNode`, `LineageEdgeRead`, `LineageGraph`), `audit.py` (`AuditRead`). `__init__.py`
re-exports these plus `PolicyInput`/`PolicyResult` from `okapi_shared`.

### `apps/api/src/okapi_api/main.py`

Instantiates `FastAPI`, calls `configure_logging()`, registers the 5 routers under
`/api/v1`, registers the `GateDenied → 403` exception handler, exposes `GET /health`.

### `packages/policies/` — OPA / Rego bundle

| File | Package | Rule |
|------|---------|------|
| `authz.rego` | `okapi.authz` | `result = {allow, allowed_fields, reason}`. `allow` iff `rbac.allow && abac.allow && hipaa.allow`. Read by `OpaPolicyClient`. |
| `rbac.rego` | `okapi.rbac` | Role × action × `field_category`: compliance_officer reads all; clinician r/w clinical+phi; researcher reads research; ai_agent reads. |
| `abac.rego` | `okapi.abac` | `attributes.clearance_level` ≥ required for the category (`phi`:3, `clinical`:2, `research`:1). |
| `compliance/hipaa.rego` | `okapi.compliance.hipaa` | Default allow; **deny** if `actor_type == "ai_agent"` and `field_category == "phi"` and `acting_on_behalf_of` is null. |
| `compliance/dpdp.rego`, `cdsco.rego` | … | Pass-through stubs (pluggability placeholders). |
| `tests/authz_test.rego` | — | 5 `opa test` cases (clinician reads PHI, AI blocked, researcher can't write, result shape allow/deny). |

### `scripts/`

| File | What it does |
|------|--------------|
| `seed.py` | Idempotent: 3 human users (`clinician`/`researcher`/`compliance_officer`) + 1 `ai_agent`, all password `okapi-dev`; demo document "Demo Patient Record" with 3 fields (one PHI + sign-off) each at v1. |
| `demo.py` | 10-step scripted walkthrough against a running API (tokens → doc+fields → edits → merge → lineage → gated read → AI-vs-PHI → tamper+integrity → audit → policy-flip note). |
| `bootstrap.sh`, `migrate.sh`, `fmt.sh` | thin wrappers over `uv` / `alembic` / `ruff`+`black`. |

### Root / tooling

`pyproject.toml` (uv workspace + ruff/black/mypy/pytest config), `apps/api/pyproject.toml`
(deps incl. `python-multipart`), `apps/api/alembic.ini` (`%(here)s` paths), `Makefile`
(`sync run test lint fmt typecheck check migrate revision seed demo opa-serve opa-test compose-up/down`),
`infra/` (docker-compose api+opa+postgres, Dockerfile), `.github/workflows/ci.yml`,
`.tools/opa.exe` (gitignored, for local `opa test` / `opa run`).

---

## 5. Configuration (env, `OKAPI_` prefix)

| Var | Default | Use |
|-----|---------|-----|
| `OKAPI_DATABASE_URL` | `postgresql+psycopg://okapi:okapi@localhost:5432/okapi` | app DB |
| `OKAPI_OPA_URL` | `http://localhost:8181` | OPA sidecar |
| `OKAPI_JWT_SECRET` | `change-me-in-env` | JWT signing |
| `OKAPI_JWT_ALGORITHM` | `HS256` | |
| `OKAPI_ACCESS_TOKEN_TTL_SECONDS` | `900` | token lifetime |
| `OKAPI_ANTHROPIC_API_KEY` | `""` | unused until extraction/RAG are built |

Tests read `OKAPI_TEST_DATABASE_URL` (default `…@localhost:55432/okapi_test`).

---

## 6. Testing

| Kind | Files | Needs |
|------|-------|-------|
| Unit | `test_health`, `test_models`, `test_gate`, `test_versioning_lineage`, `test_integrity_service`, `packages/shared/tests/test_contracts` | nothing |
| Integration (skip w/o DB) | `test_field_repository` (CTE + merge), `test_write_read_flow` (full HTTP, OPA stubbed) | Postgres |
| Policy | `packages/policies/tests/authz_test.rego` | `opa` binary |

`conftest.py`: `engine` (session-scoped, skips if no DB, `drop_all`+`create_all`),
`db_session` (savepoint rollback per test), `api_client` (`TestClient` with `get_session`
→ test engine and `get_policy_client` → `StubPolicyClient`).

Run: `uv run pytest -q` · `uv run mypy` · `uv run ruff check .` · `uv run black --check .` ·
`.tools/opa.exe test packages/policies`.

---

## 7. Deferred (stated for the review)

LLM key-data extraction (values entered directly); pgvector similarity / real RAG;
`/forms/*` autofill + submit; refresh tokens, TLS, secret management; stored Merkle-root
column (per-edge recomputation used instead); all of §11 (Neo4j lineage, async
propagation, multi-tenant gateway).
