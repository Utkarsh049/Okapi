# Okapi

**O**rchestrated **K**nowledge **A**ccess and **P**olicy **I**ntegrity Framework.

A high-assurance, backend-first governance platform for AI-assisted workflows in highly regulated domains (Healthcare EHRs, Clinical Trials, Pharma Manufacturing). Okapi enforces field-level authorization, non-destructive DAG versioning, cryptographic lineage hash chaining, zero-leakage semantic RAG, and automated compliance policy verification (HIPAA, DPDP, CDSCO) before any data mutation or retrieval occurs.

---

## Key Patent Mechanisms & Architecture

Okapi implements 6 core technical mechanisms designed for regulated compliance:

1. **Non-Destructive Field-Level Versioning**: Documents act as containers; every field mutation creates an immutable version node in a Directed Acyclic Graph (DAG) rather than performing an in-place overwrite.
2. **Cryptographic Lineage Hash Chaining**: Every parent-child relationship in the version tree is hash-chained:  
   $$\text{edge\_hash} = \text{SHA256}(\text{parent\_version\_id} + \text{parent\_value\_hash} + \text{child\_value\_hash})$$
3. **Dynamic Reactive Invalidation Cascades**: When an upstream field is modified or corrected, Okapi automatically walks downstream dependency graphs across documents and marks stale derived fields.
4. **Zero-Leakage Semantic RAG & Prompt Sandboxing**: Vector similarity search (pgvector with 384-dimensional dense embeddings) is strictly filtered by Verification Gate permissions *before* candidate retrieval, preventing unauthorized context leakage into LLM prompts. Context is isolated with XML sandboxing and anti-injection instructions.
5. **Signed Merkle Root Anti-Tamper Verification**: Document Merkle roots are cryptographically signed with HMAC-SHA256 on every mutation. Out-of-band database tampering (direct SQL edits altering values, edge hashes, or DAG structures) is immediately detected with exact mismatch diagnostics.
6. **Gated AI Form Auto-Completion & Human Sign-Off Barrier**: AI agents can draft form fields from source records with confidence tracking. Any field requiring clinical/regulatory sign-off enters `status="pending_signoff"`, and form submission strictly blocks (`422 Unprocessable Entity`) until authorized personnel sign off.

---

## Monorepo Layout

```
apps/
  api/            FastAPI service — Trusted Data Core, Verification Gate, AI Action Layer
packages/
  shared/         okapi-shared — pydantic contracts, enums, constants (zero I/O)
  policies/       Open Policy Agent (OPA) Rego bundle — RBAC, ABAC, HIPAA, DPDP, CDSCO
infra/            docker-compose (api + OPA sidecar + PostgreSQL 16 / pgvector), Dockerfile
scripts/          bootstrap / dev / migrate / seed helpers
docs/             technical implementation specifications and walkthroughs
```

---

## Multi-Regime Compliance Policy Suite

The Verification Gate evaluates request metadata against policy bundles written in Open Policy Agent (OPA) Rego:

* **HIPAA (US Healthcare)**:
  * Minimum Necessary Rule: Field-level access restricted to active clinical treatment context.
  * AI Delegation Boundaries: AI agents strictly prohibited from accessing psychotherapy notes or unredacted identifiers without human delegation.
  * Business Associate Agreement (BAA) enforcement for third-party entities.
* **DPDP Act 2023 (India Data Protection)**:
  * Purpose Limitation: Data access strictly evaluated against specific processing purposes.
  * Consent Withdrawal: Operations on withdrawn data are immediately blocked.
  * Minor Data Protection: Strict parental consent verification for minors.
* **CDSCO (India Pharma Regulatory)**:
  * Released Lot Immutability: Batch manufacturing records and QA release signatures cannot be modified once certified.
  * Qualified Person Sign-Off: Lot release requires authorized regulatory personnel.

---

## Security Hardening & Defenses

* **OWASP Defense-in-Depth Headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, `Strict-Transport-Security`, `Content-Security-Policy`, `Referrer-Policy`.
* **Payload Size Limits**: Strict 5MB request body limit preventing memory exhaustion / denial of service.
* **Token-Bucket Rate Limiter**: Thread-safe sliding-window request throttling with standard `429 Too Many Requests` and `Retry-After` headers.
* **Input Sanitization**: Automatic stripping of null bytes (`\x00`) and bidi unicode direction override sequences across all Pydantic schemas.
* **Token Security & Revocation**: Algorithm-pinned `HS256` tokens with unique `jti`, `nbf`, `iat`, `exp` claims and thread-safe revocation blacklist (`POST /api/v1/auth/revoke`).

---

## Tooling & Verification Suite

* **uv Workspace**: Single lockfile (`uv.lock`), centralized tool configuration (`pyproject.toml`).
* **Python 3.12** (`.python-version`).
* **Static Analysis**: `ruff check .`, `black --check .`, and `mypy --strict` (zero errors across 63 source files).
* **Automated Tests**: **81/81 Pytest tests** and **19/19 OPA policy unit tests** passing.

---

## Quickstart

### 1. Prerequisites
* [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
* [Open Policy Agent (OPA)](https://www.openpolicyagent.org/docs/latest/#1-download-opa) binary
* PostgreSQL 16 with `pgvector` extension (or run via `docker compose`)

### 2. Environment Setup
```bash
# Sync dependencies
uv sync

# Setup environment variables
cp .env.example .env

# Run database migrations
uv run --package okapi-api alembic -c apps/api/alembic.ini upgrade head
```

### 3. Run Development Stack
```bash
# Single command starts OPA on :8181 and FastAPI on :8000
make dev
# or:
./scripts/dev.sh
```

Interactive API documentation will be available at: **http://localhost:8000/docs**

---

## Running Verification & Quality Gates

```bash
# Run full Pytest test suite (automatically reads DB from .env)
make test
# or run with explicit alias:
OKAPI_TEST_DATABASE_URL="postgresql+psycopg://okapi_user:okapi_password@localhost:5432/okapi" uv run pytest

# Run OPA policy test suite
make opa-test

# Run all quality gates (lint + typecheck + all tests)
make gate
```

---

## Team & Ownership

* **Utkarsh (23BCT0148)** — Verification Gate, Rego Policies, Lineage DAG, Merkle Anti-Tamper Hardening.
* **Mohammed Ehtishaam T (23BCE2357)** — AI Action Layer, pgvector Embeddings, Field-Scoped Semantic RAG, AI Form Auto-Fill.
* **Prateek Batra (23BCE2087)** — Data Architecture, API Layer & Security Middleware, CI/CD Pipeline, Benchmarking.

---

## Documentation

* [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) — Comprehensive technical reference, request flow, and full API endpoint documentation.
* [docs/DEMO.md](docs/DEMO.md) — Step-by-step end-to-end scenario walkthrough.
* [STRUCTURE.md](STRUCTURE.md) — Detailed monorepo file and directory structure map.
