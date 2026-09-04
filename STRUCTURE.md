# Repository Structure

Comprehensive mapping of files and directories across the Okapi workspace.

```
Okapi/
├── apps/
│   └── api/                     # FastAPI deployment (okapi-api)
├── packages/
│   ├── shared/                  # Zero-I/O contracts and enums (okapi-shared)
│   └── policies/                # Open Policy Agent Rego compliance bundle
├── infra/                       # Docker Compose, OPA sidecar, Dockerfile
├── scripts/                     # Dev helpers, seeders, and benchmark harnesses
└── docs/                        # Specifications, walkthroughs, and architecture refs
```

---

## 1. Root & Workspace Configuration

| Path | Purpose |
|---|---|
| `pyproject.toml` | Workspace root defining members (`apps/api`, `packages/shared`) and shared tool config (`ruff`, `black`, `mypy --strict`, `pytest`). |
| `uv.lock` | Deterministic lockfile across all Python dependencies. |
| `.python-version` | Pins Python `3.12`. |
| `.pre-commit-config.yaml` | Git pre-commit hooks for formatters and linters. |
| `.env.example` | Environment configuration template (`OKAPI_` prefix). |
| `Makefile` | Build, test, lint, format, migration, and dev server shortcuts. |
| `README.md` | Monorepo overview, patent mechanisms, and quickstart guide. |
| `MECHANISM.md` | Technical mechanisms, mathematical formulations, worked examples, and Section 3(k) Indian patent claims mapping. |
| `STRUCTURE.md` | This file. |
| `benchmark_results.md` | Empirical benchmark results report and comparative architectural baseline matrix. |
| `benchmark_results.json` | Machine-readable benchmark outputs and statistical metrics. |
| `timeline.md` | Milestone progress (git-ignored). |

---

## 2. `apps/api/` — FastAPI Service (`okapi-api`)

### `apps/api/src/okapi_api/`

#### `core/` — Security, Configuration & Middleware
| File | Purpose |
|---|---|
| `config.py` | Environment configuration loaded via `pydantic-settings`. |
| `security.py` | JWT creation, claim validation, password hashing, and algorithm pinning. |
| `token_store.py` | In-memory thread-safe token revocation store (`POST /auth/revoke`). |
| `hashing.py` | SHA-256 value/edge hashing, Merkle root accumulation, and HMAC-SHA256 signing. |
| `middleware.py` | `SecurityHeadersMiddleware` (OWASP headers) and `PayloadSizeLimitMiddleware` (5MB limit). |
| `rate_limit.py` | `TokenBucketRateLimiter` sliding-window throttling and FastAPI `RateLimiter` dependency. |
| `sanitization.py` | Input sanitization utilities (null byte and bidi control character stripping). |
| `logging.py` | Structured JSON stdout logging handler. |
| `deps.py` | FastAPI dependency injection hub assembling services, repositories, and Gate. |

#### `gate/` — Verification & Compliance Gate (Layer 2 Choke Point)
| File | Purpose |
|---|---|
| `gate.py` | Layer 2 single choke point enforcing ABAC/RBAC and compliance rules before data access. |
| `policy_client.py` | HTTP client communicating with OPA sidecar (`OpaPolicyClient` and `StubPolicyClient`). |

#### `services/` — Business Logic & Orchestration
| File | Purpose |
|---|---|
| `versioning_service.py` | Non-destructive field-level versioning and automated vector embedding generation. |
| `lineage_service.py` | Lineage DAG edge hash chaining. |
| `propagation_service.py` | Walks cross-document reference graphs and flags downstream fields as `stale`. |
| `edit_service.py` | Gated write orchestrator (Gate $\to$ versioning $\to$ lineage $\to$ propagation $\to$ Merkle signing). |
| `embedding_service.py` | Dense 384-dimensional $L_2$-normalized dense embeddings and cosine similarity. |
| `rag_service.py` | Zero-leakage field-scoped vector retrieval with defensive XML prompt sandwiching. |
| `extraction_service.py` | LLM-backed key-data extraction with XML sandboxing and regex fallback. |
| `form_fill_service.py` | AI form auto-completion and human sign-off submission barrier (Patent Mechanism 4.6). |
| `integrity_service.py` | Lineage hash chain and signed Merkle root anti-tamper verification. |
| `retrieval_service.py` | Read flow orchestrator (Gate check $\to$ RAG query $\to$ audit log). |

#### `repositories/` — Persistence Layer (PostgreSQL / pgvector)
| File | Purpose |
|---|---|
| `document_repository.py` | Document container CRUD, Merkle root signature persistence, and compliance-metadata partial updates. |
| `field_repository.py` | Fields, versions, lineage edges, references, and recursive CTE ancestry. |
| `embedding_repository.py` | Vector embedding storage and pgvector similarity queries. |
| `audit_repository.py` | Immutable append-only audit log storage. |
| `user_repository.py` | User lookups and credentials verification. |

#### `models/` — SQLAlchemy ORM Models
| File | Purpose |
|---|---|
| `document.py` | `documents` table (`id`, `title`, `doc_type`, `merkle_root`, `merkle_signature`, `last_verified_at`) plus 10 nullable compliance-metadata columns (`consent_status`, `consent_purposes`, `is_minor`, `parental_consent`, `batch_status`, `is_lot_release`, `is_sae`, `deidentified`, `irb_waiver`, `baa_active`) forwarded to OPA by `Gate._doc_meta`. |
| `field.py` | `fields` and `field_versions` tables (DAG parent arrays, content hashes). |
| `field_embedding.py` | `field_embeddings` table (pgvector 384-d dense embeddings per version). |
| `lineage.py` | `lineage_edges` table (hash-linked DAG edges). |
| `reference.py` | `field_references` table (cross-document dependency links). |
| `compliance.py` | `compliance_rules` table (active regulatory regimes registry). |
| `audit.py` | `audit_log` table (append-only evaluation records). |
| `user.py` | `users` table (roles, hashed passwords, ABAC attributes). |

#### `api/v1/` — HTTP Endpoints
| File | Purpose |
|---|---|
| `auth.py` | `POST /auth/token`, `POST /auth/delegate`, `POST /auth/revoke`. |
| `documents.py` | `POST /documents`, `PATCH /{id}/compliance` (compliance_officer-only), `POST /{id}/fields`, `PATCH /{id}/fields/{field_id}`, `POST /{id}/extract`, `POST /{id}/query`, `GET /{id}/lineage`, `GET /{id}/integrity`. |
| `fields.py` | `POST /fields/{field_id}/signoff`. |
| `forms.py` | `POST /forms/{form_id}/autofill`, `POST /forms/{form_id}/submit`. |
| `audit.py` | `GET /audit`. |
| `health.py` | `GET /health/live`, `GET /health/ready`. |

---

## 3. `packages/policies/` — OPA / Rego Bundle

| File | Purpose |
|---|---|
| `authz.rego` | Aggregates decisions across RBAC, ABAC, and compliance regimes. |
| `rbac.rego` | Role-based permissions (clinician, researcher, compliance_officer, auditor, chemist, ai_agent). |
| `abac.rego` | Attribute-based clearance evaluation (`phi`:3, `clinical`:2, `research`:1). |
| `compliance/hipaa.rego` | Minimum necessary rule, AI delegation constraints, BAA enforcement. |
| `compliance/dpdp.rego` | Purpose limitation, consent withdrawal, and minor data protection. |
| `compliance/cdsco.rego` | Pharma batch release lot immutability and qualified person sign-off. |
| `tests/authz_test.rego` | OPA unit test assertions covering RBAC, ABAC, and decision shapes. |
| `tests/compliance_test.rego` | OPA unit test assertions covering HIPAA, DPDP, and CDSCO regimes. |

---

## 4. `apps/api/tests/` — Test Suites (84 Tests)

| Directory | Purpose | Key Files |
|---|---|---|
| `security/` | Adversarial attacks & security boundaries | `test_gate_bypass_attempts.py`, `test_privilege_escalation.py`, `test_tamper_detection.py`, `test_cross_tenant_leakage.py` |
| `integration/` | End-to-end flows against PostgreSQL | `test_anti_tamper_integrity.py`, `test_gated_form_submission.py`, `test_input_fuzzing.py`, `test_zero_leakage_rag.py`, `test_field_embeddings.py`, `test_compliance_regimes.py`, `test_auth_security.py`, `test_signoff_security.py`, `test_benchmark_harness.py`, `test_seed_demo.py`, `test_write_read_flow.py` |
| `unit/` | Pure business logic and cryptographic tests | `test_merkle_crypto.py`, `test_embedding_service.py`, `test_extraction_service.py`, `test_form_fill_service.py`, `test_rag_security.py`, `test_rate_limiting.py`, `test_security_middleware.py`, `test_gate.py`, `test_models.py`, `test_versioning_lineage.py`, `test_security_auth.py`, `test_integrity_service.py`, `test_health.py` |

---

## 5. `scripts/`

| File | Purpose |
|---|---|
| `bootstrap.sh` | First-time local setup. |
| `dev.sh` | Starts OPA + FastAPI for local development; downloads a standalone OPA binary into `.tools/` if none is on `PATH`. |
| `fmt.sh` | Formatting shortcut (`ruff check --fix`, `black`). |
| `migrate.sh` | Runs Alembic migrations. |
| `seed.py` | Idempotently provisions 6 multi-clearance users and 5 multi-regime documents with dense pgvector embeddings. |
| `demo.py` | Scripted 8-scenario end-to-end walkthrough against live server with color-coded ANSI banners. |
| `benchmark.py` | Standalone empirical performance harness measuring Gate latency, Merkle DAG scaling, invalidation cascades, zero-leakage RAG, and comparative baseline matrix with JSON and Markdown export. |
