# Okapi — Implementation Reference

Comprehensive technical reference of Okapi's architecture, API surface, compliance policies, cryptographic integrity mechanisms, and file layout.

---

## 1. Status

| Phase | Milestone | State |
|---|---|---|
| **Phase 01** | AuthN/AuthZ Baseline Hardening, Token Scoping & Revocation Store (`/auth/revoke`) | **Complete & Verified** |
| **Phase 02** | Gated Sign-Off Policy Enforcement & Authorization Gate Expansion (`POST /fields/{id}/signoff`) | **Complete & Verified** |
| **Phase 03** | Multi-Regime Compliance Policy Suite (HIPAA, India DPDP Act 2023, CDSCO Pharma) | **Complete & Verified** |
| **Phase 04** | LLM Key-Data Extraction Pipeline with XML Isolation & Schema Validation (`POST /documents/{id}/extract`) | **Complete & Verified** |
| **Phase 05** | pgvector Embeddings & Field-Level Vector Store Integration (`FieldEmbedding`, `EmbeddingRepository`) | **Complete & Verified** |
| **Phase 06** | Field-Scoped Semantic RAG & Prompt Injection Defenses (`RAGService` zero-leakage sandbox) | **Complete & Verified** |
| **Phase 07** | Gated AI Form Auto-Completion & Human Sign-Off Workflow (`/forms/{id}/autofill`, `/forms/{id}/submit`) | **Complete & Verified** |
| **Phase 08** | Merkle Root Cryptographic Signing & Anti-Tamper Hardening (`merkle_root` + HMAC-SHA256) | **Complete & Verified** |
| **Phase 09** | API Security Hardening: Security Headers, Rate Limiting, 5MB Limits, & Input Sanitization | **Complete & Verified** |
| **Phase 10** | Adversarial Security & Fuzz Testing Suite (Gate bypass, privilege escalation, DB tampering, tenant isolation) | **Complete & Verified** |

**Verification Gate Metrics:**
* `pytest` Suite: **81/81 Passed** (Unit, Integration, and Adversarial Security tests)
* `opa test` Suite: **19/19 Passed** (RBAC, ABAC, HIPAA, DPDP, CDSCO policies)
* `mypy --strict`: **Clean (0 errors across 63 source files)**
* `ruff` & `black`: **Clean (100% compliant)**

---

## 2. Request Lifecycle & Gate Enforcement

```
HTTP Request
  │
  ├─► Security Middleware (SecurityHeaders, PayloadSizeLimit [5MB], RateLimiter)
  │
  ├─► Router Layer (apps/api/src/okapi_api/api/v1/*.py)
  │     └─► Validates Pydantic schemas (sanitizes null-bytes, control characters)
  │
  ├─► Service Layer (services/*.py)
  │     │
  │     ├─► Layer 2: Verification Gate (gate/gate.py) [MANDATORY PRE-CHECK]
  │     │     ├─► PolicyClient.evaluate (gate/policy_client.py)
  │     │     │     └─► Open Policy Agent (packages/policies/*.rego)
  │     │     └─► AuditRepository.record (writes immutable decision log)
  │     │
  │     ├─► Trusted Data Core (repositories/*.py)
  │     │     ├─► Versioning & DAG Linkage (FieldRepository, LineageService)
  │     │     ├─► pgvector Dense Embeddings (EmbeddingRepository)
  │     │     └─► Merkle Cryptographic Signing (IntegrityService)
  │     │
  │     └─► AI Action Layer (RAGService, ExtractionService, FormFillService)
  │           └─► Context is strictly filtered by Gate permissions before retrieval
```

---

## 3. Complete API Reference

Base path: `/api/v1` (defined in `okapi_shared.constants.API_V1_PREFIX`).

### Meta Endpoints
* **`GET /health`**: Health probe. `200 -> {"status": "ok"}` (No auth required).
* **`GET /`**: Redirects to interactive OpenAPI docs (`/docs`).

### Authentication & Token Management
* **`POST /api/v1/auth/token`**: OAuth2 form login (`username`, `password`). Returns access token with claims `sub`, `role`, `actor_type`, `attributes`, `jti`, `nbf`, `iat`, `exp`.
* **`POST /api/v1/auth/revoke`**: Revokes an active token by its `jti` claim, blacklisting it in the thread-safe `TokenStore`.

### Document Containers
* **`POST /api/v1/documents`**: Creates a new document container (`title`, `doc_type`).
* **`GET /api/v1/documents/{document_id}`**: Retrieves document metadata, signed `merkle_root`, `merkle_signature`, and `last_verified_at`.

### Field Registration & Gated Writes
* **`POST /api/v1/documents/{document_id}/fields`**: Registers a field on a document (`field_key`, `field_type`, `requires_signoff`, `category`, `value`).
* **`PATCH /api/v1/documents/{document_id}/fields/{field_id}`**: Gated field mutation. Enforces `Gate.check_write` $\to$ appends `field_versions` $\to$ computes `edge_hash` in `lineage_edges` $\to$ flags downstream dependents as `stale` $\to$ recomputes and cryptographically signs document `merkle_root`.

### Field Extraction & AI Operations
* **`POST /api/v1/documents/{document_id}/extract`**: LLM extraction of key clinical/scientific data from unstructured text with XML sandboxing and regex deterministic fallback. Optional `auto_register=True`.
* **`POST /api/v1/documents/{document_id}/query`**: Zero-leakage field-scoped RAG. Gate filters all document fields $\to$ vector similarity search restricted to allowed fields $\to$ prompt sandwiching $\to$ synthesizes answer.
* **`POST /api/v1/forms/{form_id}/autofill`**: Multi-document AI form auto-completion. Drafts target form fields with `is_ai_generated=True` and `status="pending_signoff"` if sign-off is required.
* **`POST /api/v1/forms/{form_id}/submit`**: Form submission barrier (Patent Mechanism 4.6). Strictly returns `422 Unprocessable Entity` if any field remains in `pending_signoff` state.

### Lineage, Integrity & Audit
* **`GET /api/v1/documents/{document_id}/lineage`**: Traverses the version DAG via recursive CTEs, returning full node and edge graphs with content and edge hashes.
* **`GET /api/v1/documents/{document_id}/integrity`**: Verifies all `value_hash`es, `edge_hash`es, document `merkle_root`, and HMAC signature to detect out-of-band database tampering.
* **`POST /api/v1/fields/{field_id}/signoff`**: Authorized human sign-off on a pending field version, transitioning `status` from `pending_signoff` to `active`.
* **`GET /api/v1/audit`**: Filterable, append-only query log of all Verification Gate decisions.

---

## 4. Module & File Map

### `apps/api/src/okapi_api/`

* **`core/`**:
  * `config.py`: Environment configuration via `pydantic-settings`.
  * `security.py`: JWT generation, claim validation, password hashing, and token validation.
  * `token_store.py`: In-memory thread-safe JWT revocation store.
  * `hashing.py`: Deterministic content hashes, DAG edge hashes, Merkle root accumulation, and HMAC cryptographic signing.
  * `middleware.py`: `SecurityHeadersMiddleware` (OWASP headers) and `PayloadSizeLimitMiddleware` (5MB limit).
  * `rate_limit.py`: `TokenBucketRateLimiter` and FastAPI `RateLimiter` dependency.
  * `sanitization.py`: Null byte (`\x00`) and bidi unicode override sanitizer.
  * `deps.py`: Dependency injection hub assembling repositories, services, and Gate instances.
* **`gate/`**:
  * `gate.py`: Layer 2 single choke point enforcing ABAC/RBAC/Compliance before data operations.
  * `policy_client.py`: HTTP policy client communicating with OPA sidecar (`OpaPolicyClient` and `StubPolicyClient`).
* **`services/`**:
  * `versioning_service.py`: Field-level non-destructive versioning with automatic vector embedding generation.
  * `lineage_service.py`: Computes DAG edge hash chains for parent-child lineage.
  * `propagation_service.py`: Walks cross-document references and flags downstream dependents as `stale`.
  * `edit_service.py`: Write flow orchestrator (Gate check $\to$ versioning $\to$ lineage $\to$ propagation $\to$ Merkle signing).
  * `embedding_service.py`: Dense 384-dimensional $L_2$-normalized vector embeddings and cosine similarity.
  * `rag_service.py`: Field-scoped semantic retrieval with defensive XML prompt sandwiching.
  * `extraction_service.py`: LLM-backed key-data extraction with prompt injection defense and deterministic fallback.
  * `form_fill_service.py`: Gated multi-document AI form drafting and sign-off barrier submission.
  * `integrity_service.py`: Hash-chain and signed Merkle root anti-tamper verification.
  * `retrieval_service.py`: Read flow orchestrator.
* **`repositories/`**:
  * `document_repository.py`: Document container operations and Merkle signature updates.
  * `field_repository.py`: Field CRUD, version history, lineage edges, references, and recursive CTE ancestry.
  * `embedding_repository.py`: Field-level dense vector storage and cosine similarity queries.
  * `audit_repository.py`: Immutable audit logging.
  * `user_repository.py`: User retrieval and authentication lookups.
* **`models/`**:
  * `document.py`, `field.py`, `lineage.py`, `field_embedding.py`, `reference.py`, `audit.py`, `compliance.py`, `user.py`.

---

## 5. Security & Verification Summary

| Category | Defense Mechanism | Test Coverage |
|---|---|---|
| **Gate Bypass** | All repositories are unreachable without passing `Gate.check_*` | [`test_gate_bypass_attempts.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/security/test_gate_bypass_attempts.py) |
| **Privilege Escalation** | Algorithm pinning (HS256), cryptographic signature check, claims verification | [`test_privilege_escalation.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/security/test_privilege_escalation.py) |
| **Out-of-Band Tampering** | Signed document Merkle root + per-edge hash chain verification | [`test_tamper_detection.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/security/test_tamper_detection.py), [`test_anti_tamper_integrity.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_anti_tamper_integrity.py) |
| **Data Leakage** | Gate filters field keys *before* vector search or prompt assembly | [`test_cross_tenant_leakage.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/security/test_cross_tenant_leakage.py), [`test_zero_leakage_rag.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_zero_leakage_rag.py) |
| **Prompt Injection** | XML sandboxing (`<untrusted_document>`, `<permitted_context>`) + system prompt framing | [`test_extraction_service.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/unit/test_extraction_service.py), [`test_rag_security.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/unit/test_rag_security.py) |
| **Input Fuzzing** | SQL injection, XSS vectors, null bytes, and traversal strings handled safely | [`test_input_fuzzing.py`](file:///home/utkarsh/Desktop/Okapi/apps/api/tests/integration/test_input_fuzzing.py) |
