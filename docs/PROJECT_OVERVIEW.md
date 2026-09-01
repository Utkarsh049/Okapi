# Okapi — Project Overview

*Orchestrated Knowledge Access and Policy Integrity Framework*

*Last updated: 2026-09-01*

This document explains what Okapi is, how a request actually moves through it, and what
every file in the repo is for. It reflects the code as it exists right now — not the
original design docs, not what was planned, what's actually running.

---

## 1. What Okapi is, in plain language

Okapi is a backend for storing and editing sensitive records — patient charts, clinical
trial data, pharmaceutical batch records — in industries where you legally cannot just
`UPDATE` a row and move on. Every change has to be traceable, every access has to be
justified against a rulebook, and an AI agent touching the data has to be held to a
stricter standard than a human.

It solves that with one architectural idea, applied consistently everywhere: **nothing
reads or writes a field without first asking a policy engine "is this allowed?", and
every answer — yes or no — is permanently logged.** Nothing bypasses this. There is no
back door, no admin override, no direct repository call that skips it.

On top of that gate sit three more ideas:

- **Nothing is ever overwritten.** Editing a field doesn't change a row — it adds a new
  version linked to the version(s) it came from. The full history, forever, is the
  data model, not an afterthought bolted onto it.
- **The history is tamper-evident.** Every link between versions is a hash of its
  parent and child; the whole document's set of links rolls up into a single signed
  fingerprint. If someone edits the database directly instead of going through the API,
  recomputing the hashes catches it.
- **An AI agent is a second-class citizen by design.** It can read only what a human
  explicitly delegated to it, it's flagged as AI-authored in the audit trail, and
  anything it drafts that needs a human sign-off is held in a pending state until a
  real clinician or compliance officer approves it.

The three compliance rulebooks currently wired in — **HIPAA** (US healthcare), **DPDP**
(India's Digital Personal Data Protection Act), and **CDSCO** (India's pharma
manufacturing/clinical-trial regulator) — are not hardcoded `if` statements in Python.
They're written as standalone policy files in a language called Rego, evaluated by a
separate service (Open Policy Agent / OPA) that the API calls out to on every single
field access. Changing a rule means editing a policy file and restarting OPA — no
application redeploy.

---

## 2. The request lifecycle — how a call actually flows

Take the most consequential path: a clinician edits a patient's diagnosis field.

```
PATCH /api/v1/documents/{doc_id}/fields/{field_id}
        │
        ▼
1. Auth          JWT is decoded and verified (signature, expiry, not-yet-valid,
                  required claims). Rejected here → 401. The token carries the
                  actor's role, whether they're human or an AI agent, and their
                  ABAC attributes (department, clearance_level, ...).
        │
        ▼
2. Rate limit    Every request to a sensitive endpoint is throttled per
                  (client IP + hashed auth token). Too many → 429.
        │
        ▼
3. The Gate      EditService asks Gate.check_write(actor, document, field).
                  The Gate builds a PolicyInput — who's asking, what action,
                  which field, and ~13 pieces of document metadata (category,
                  consent status, batch status, is_minor, is_sae, ...) — and
                  POSTs it to OPA.
        │
        ▼
4. OPA           packages/policies/authz.rego ANDs together five independent
                  verdicts: RBAC (does this role do this action at all),
                  ABAC (does this actor's clearance_level clear this field's
                  category), HIPAA, DPDP, CDSCO. ALL must agree, or it's a
                  deny. OPA returns {allow, reason}.
        │
        ▼
5. Audit         Whatever OPA said — allow or deny — is written to audit_log
                  as a permanent row, before the Gate returns control. A
                  denial is logged exactly like an approval.
        │
        ▼
6a. Denied       Gate raises GateDenied → FastAPI maps it to HTTP 403.
    No repository write ever happens on this path.
        │
6b. Allowed      VersioningService creates a new FieldVersion (never mutates
                  the old one) → LineageService hash-chains it to its
                  parent(s) → PropagationService flags any other document's
                  fields that referenced the old value as now stale →
                  EditService recomputes the document's Merkle root and
                  re-signs it with HMAC-SHA256.
        │
        ▼
    200 OK — the new version, its hash, its parent(s), timestamp.
```

A **read** (`POST /documents/{id}/query`) follows the same gate pattern but
per-field: the Gate is asked once per field on the document, and only the
fields that come back `allow` are ever fetched from the database, let alone
handed to the retrieval/RAG layer. A field the actor isn't cleared for isn't
"redacted" after the fact — it's never queried in the first place.

**Delegating to an AI agent** is a separate, explicit step: a clinician or
compliance officer calls `POST /auth/delegate` with an AI agent's email and
gets back a token for that agent carrying `acting_on_behalf_of: <their own
sub>`. Only then can HIPAA's Rule 1 (`hipaa.rego`) let that agent's reads of
PHI through — an agent with no delegation is denied at the compliance layer
regardless of what RBAC/ABAC say.

**An AI-drafted form field** that requires sign-off doesn't error out — it's
written as a real version with `status="pending_signoff"`. The form can't be
submitted (`POST /forms/{id}/submit` returns 422) until every such field has
been reviewed and moved to `active` via `POST /fields/{id}/signoff`, which
itself goes through the Gate.

**Detecting tampering** (`GET /documents/{id}/integrity`) doesn't trust
anything stored on the document row. It re-reads every version and edge from
scratch, recomputes every hash and the Merkle root independently, and only
then compares against what's stored and re-verifies the HMAC signature. A
direct `UPDATE field_versions SET value = ...` in Postgres, bypassing the API
entirely, is caught here because the recomputed hash won't match.

---

## 3. What each file contributes

### Top level

| File | Purpose |
|---|---|
| `README.md` | Project pitch, architecture summary, quickstart, team ownership. |
| `STRUCTURE.md` | Directory-by-directory map of the monorepo. |
| `docs/IMPLEMENTATION.md` | Full technical reference — schema, endpoints, request flow. |
| `docs/DEMO.md` | Scripted walkthrough for a review demo. |
| `Makefile` | One-word entry points (`make dev`, `make test`, `make gate`, `make demo`, ...) wrapping the `uv`/`opa`/`docker compose` commands underneath. |
| `pyproject.toml`, `uv.lock` | `uv` workspace root — pins the toolchain and dependency versions for every package in the monorepo from one lockfile. |
| `.env.example` | Every environment variable the app reads (`OKAPI_DATABASE_URL`, `OKAPI_OPA_URL`, `OKAPI_JWT_SECRET`, `OKAPI_MERKLE_SECRET`, `OKAPI_ANTHROPIC_API_KEY`, ...), documented with safe local defaults. |
| `.github/workflows/ci.yml` | GitHub Actions pipeline: brings up Postgres + OPA, then runs lint, `mypy --strict`, pytest, and `opa test` on every push. |
| `infra/docker-compose.yml` / `docker-compose.test.yml` | Full stack (API + OPA + Postgres/pgvector) for local dev vs. CI, respectively. |
| `infra/Dockerfile.api` | Container build for the FastAPI service. |
| `scripts/seed.py` | Idempotently creates four demo users (clinician, researcher, compliance officer, AI agent) and one demo patient record with starting field values. |
| `scripts/demo.py` | Scripted end-to-end walkthrough of the request lifecycle above, runnable against a live stack. |
| `scripts/benchmark.py` | Latency benchmarks for the edit pipeline and Merkle verification. |
| `scripts/dev.sh`, `bootstrap.sh`, `migrate.sh`, `fmt.sh` | Shell wrappers the Makefile targets call into. |

### `packages/shared/` — zero-I/O contracts everyone depends on

| File | Purpose |
|---|---|
| `okapi_shared/enums.py` | `ActorType` (human / ai_agent), `Decision` (allow / deny), `EdgeAction` (read / write / signoff / manage_compliance), `ReferenceStatus` (current / stale) — the vocabulary every layer, including the Rego policies, agrees on. |
| `okapi_shared/contracts.py` | The exact pydantic shapes exchanged with OPA: `GateActor`, `PolicyInput`, `PolicyResult`. This *is* the API contract between the Python app and the policy engine. |
| `okapi_shared/constants.py` | `API_V1_PREFIX`, the hash algorithm name, and the OPA decision path the policy client reads. |

### `packages/policies/` — the rulebook, in Rego

| File | Purpose |
|---|---|
| `authz.rego` | The aggregate decision. Imports RBAC, ABAC, and all three compliance packages and ANDs them together — every layer must independently allow, or the whole thing denies. This is the only package `PolicyClient` talks to. |
| `rbac.rego` | Structural role rules: who's even allowed to attempt this class of action (e.g. researchers can only read `research`-category fields; only compliance officers can `manage_compliance`). |
| `abac.rego` | Attribute-based check: does the actor's `clearance_level` meet the minimum required for the field's category (`phi`→3, `clinical`→2, `research`→1). |
| `compliance/hipaa.rego` | AI-without-delegation can't read PHI; researchers can't read PHI without de-identification or an IRB waiver; contractors can't read PHI without an active BAA. |
| `compliance/dpdp.rego` | Withdrawn consent blocks all non-compliance-officer access; a purpose-limited record blocks access outside its registered purposes; minors' data needs parental consent or clearance ≥ 4. |
| `compliance/cdsco.rego` | Released/recalled/quarantined batches are write-immutable; lot-release sign-off needs clearance ≥ 4; SAE (serious adverse event) records can't be written by clearance < 3. |
| `tests/authz_test.rego`, `tests/compliance_test.rego` | The 19 `opa test` cases covering the above. |

### `apps/api/src/okapi_api/` — the service

**`gate/`** — the choke point every write and read passes through
| File | Purpose |
|---|---|
| `gate.py` | `Gate` class: builds `PolicyInput` (including the 10 compliance-metadata fields — consent, minor/parental-consent, batch status, lot-release, SAE, de-identified, IRB waiver, BAA), calls the policy client, writes the audit row, and raises `GateDenied` on a deny. Has one `_decide` per-field method (used by write/signoff/read) plus a separate `check_manage_compliance` for the document-level compliance-metadata endpoint. |
| `policy_client.py` | `OpaPolicyClient` — the real HTTP client to the OPA sidecar. `StubPolicyClient` — an in-memory stand-in used by unit tests so they don't need a live OPA. |

**`models/`** — the SQLAlchemy schema (8 tables)
| File | Purpose |
|---|---|
| `base.py` | Declarative base + shared Postgres enum column types. |
| `document.py` | `documents` — containers only, no content. Carries the Merkle root/signature and the 10 nullable compliance-metadata columns the Gate reads. |
| `field.py` | `fields` (the atomic unit — key, type, category, whether it needs sign-off) and `field_versions` (the actual values; `parent_version_id` is an *array*, which is what makes this a DAG and not a linked list). |
| `field_embedding.py` | `field_embeddings` — one vector per field version, used for semantic retrieval. |
| `lineage.py` | `lineage_edges` — the hash-chained parent→child links. |
| `reference.py` | `field_references` — cross-document dependency edges that drive staleness propagation. |
| `audit.py` | `audit_log` — append-only, one row per Gate decision. |
| `user.py` | `users` — identity plus the JSONB `attributes` bag ABAC reads (`clearance_level`, `department`, `employment_type`). |
| `compliance.py` | `compliance_rules` — a registry of which Rego packages are active; doesn't hold rule logic itself. |

**`repositories/`** — one class per table cluster, all raw SQLAlchemy, no business logic
| File | Purpose |
|---|---|
| `document_repository.py` | CRUD on `documents`, plus `update_compliance()` for the compliance-metadata PATCH endpoint. |
| `field_repository.py` | The heaviest one: field/version CRUD, `get_head_version` (with a guarantee of strictly increasing `created_at` so rapid-fire edits can't tie), lineage edges, cross-document references, and `ancestors()` — a recursive CTE that walks the full transitive parent set of a version. |
| `audit_repository.py` | Append-only `audit_log` writes and filtered reads (by actor, actor type, document, decision). |
| `embedding_repository.py` | Stores/searches `field_embeddings`; `search_similar` dedupes to the best-scoring embedding per field before ranking, so one field's edit history can't crowd the top-k results. |
| `user_repository.py` | Lookup by id / email for auth. |

**`services/`** — orchestration; each one composes repositories and the Gate, never the other way around
| File | Purpose |
|---|---|
| `edit_service.py` | The write pipeline: Gate check → new version → hash-chain link → propagate staleness → recompute and re-sign the document's Merkle root. |
| `versioning_service.py` | Creates a `FieldVersion` and, if an embedding repo is wired, immediately computes and stores its vector embedding. |
| `lineage_service.py` | Turns a set of parent version ids into hash-chained `lineage_edges`; raises `InvalidParentVersionError` (→ 400) instead of silently dropping a bad parent id. |
| `propagation_service.py` | Walks `field_references` pointing at an edited field and flips them to `stale`. |
| `embedding_service.py` | Deterministic, dependency-free 384-dim text embedding (SHA256-seeded hashing trick) plus cosine similarity — no external embedding API required. |
| `rag_service.py` | Field-scoped retrieval: filters to Gate-permitted fields, does a top-k semantic search over just those, wraps the result in an XML "prompt sandwich" with escaping to defend against prompt injection, and calls Claude if an API key is configured (falls back to a deterministic synthesized answer otherwise). |
| `retrieval_service.py` | Thin orchestrator: `Gate.check_fields` → `RAGService.retrieve` over only the allowed subset, reporting both `allowed_fields` and `withheld_fields`. |
| `extraction_service.py` | Pulls structured fields out of raw clinical text — calls Claude with an anti-injection system prompt if configured, otherwise a regex-based deterministic fallback (diagnosis, BP, heart rate, medication, cohort size). |
| `form_fill_service.py` | AI form autofill: matches target fields to source fields by exact key or semantic similarity, drafts a version for each (gated through `Gate.check_fields` on both source and target), and marks anything `requires_signoff` as `pending_signoff`. `submit_form` hard-blocks (422) while any field is still pending. |
| `integrity_service.py` | Independent recomputation of every value hash, edge hash, and the Merkle root + HMAC signature — the anti-tamper check. Never trusts the stored root; always rebuilds it from the versions and edges themselves. |

**`api/v1/`** — the HTTP surface (FastAPI routers, no business logic)
| File | Purpose |
|---|---|
| `auth.py` | `POST /auth/token` (login, rate-limited by IP+username), `POST /auth/delegate` (clinician/compliance-officer only — issues a scoped AI-agent token), `POST /auth/revoke` (logout via jti blacklist). |
| `documents.py` | Document create, the compliance-metadata `PATCH`, field registration, text extraction (`/extract`), field edit (`PATCH .../fields/{id}`), RAG query (`/query`), lineage graph (`GET .../lineage`), integrity check (`GET .../integrity`). |
| `fields.py` | `POST /fields/{id}/signoff` — the human-approval action for a gated field. |
| `forms.py` | `POST /forms/{id}/autofill`, `POST /forms/{id}/submit`. |
| `audit.py` | `GET /audit` — filterable, read-only. |

**`schemas/`** — pydantic request/response bodies, one file per resource (`document.py`, `field.py`, `auth.py`, `audit.py`, `extraction.py`, `form.py`, `lineage.py`, `read.py`). Every string-input schema routes through `sanitize_text` (`core/sanitization.py`) to strip null bytes and bidi-override unicode tricks before it reaches business logic.

**`core/`** — cross-cutting infrastructure
| File | Purpose |
|---|---|
| `config.py` | `Settings` (pydantic-settings) — every `OKAPI_`-prefixed env var, including separate `jwt_secret` and `merkle_secret` (a leaked JWT secret shouldn't also let someone forge integrity signatures). |
| `security.py` | Password hashing (bcrypt) and JWT encode/decode with algorithm pinning and required-claims enforcement. |
| `rate_limit.py` | `TokenBucketRateLimiter` — thread-safe sliding-window limiter; keys are a SHA256 hash of the full auth header (not a prefix, which would collide across every user since JWT headers are near-identical). |
| `token_store.py` | In-memory JWT revocation blacklist (jti → expiry), self-evicting. |
| `sanitization.py` | Input cleaning (`sanitize_text`) and field-key format validation (`validate_field_key`). |
| `middleware.py` | `SecurityHeadersMiddleware` (CSP, HSTS, nosniff, etc.) and `PayloadSizeLimitMiddleware` (5MB cap). |
| `logging.py` | JSON-structured log formatting. |
| `deps.py` | All FastAPI dependency wiring — every repository, service, and the Gate itself is constructed here and injected into routers. This is the one place that knows how everything connects. |

**`db/`**
| File | Purpose |
|---|---|
| `session.py` | The one place a SQLAlchemy `Session` is created; sync by design (FastAPI runs sync routes in a threadpool). |
| `migrations/versions/0001_core_schema.py` | Initial schema — the 8 core tables. |
| `migrations/versions/c081e27bc57a_...py` | Adds Merkle root/signature columns to `documents`. |
| `migrations/versions/f0aae02ae220_...py` | Adds `field_embeddings`. |
| `migrations/versions/f6334cdc556e_...py` | Adds the 10 compliance-metadata columns to `documents` (all nullable — safe against a populated table). |

**`main.py`** — app entrypoint: registers middleware and routers, maps `GateDenied` → 403 and `InvalidParentVersionError` → 400, exposes `/health`.

### `apps/api/tests/` — 81 tests across three tiers

- **`unit/`** — services and core logic in isolation (`test_gate.py`, `test_rate_limiting.py`, `test_versioning_lineage.py`, `test_merkle_crypto.py`, `test_embedding_service.py`, `test_form_fill_service.py`, `test_rag_security.py`, `test_security_auth.py`, `test_security_middleware.py`, `test_integrity_service.py`, `test_extraction_service.py`, `test_models.py`, `test_health.py`).
- **`integration/`** — real Postgres + real OPA: field repository behavior, write/read flow, gated form submission, embeddings, anti-tamper integrity, auth security, extraction endpoint, zero-leakage RAG, and `test_compliance_regimes.py` (the DPDP/CDSCO/HIPAA live-verification suite).
- **`security/`** — adversarial: `test_gate_bypass_attempts.py`, `test_privilege_escalation.py`, `test_cross_tenant_leakage.py`, `test_tamper_detection.py`.
- **`conftest.py`** — shared fixtures (DB session, test client, seeded actors).
