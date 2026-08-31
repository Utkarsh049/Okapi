# Okapi Command Reference & Execution Guide

Comprehensive reference of all operational commands, Makefile targets, background processes, database migration tasks, and testing utilities in the Okapi repository.

---

## 1. Quick Command Cheat Sheet (TL;DR)

| Task | Quick Make Command | Underlying Command |
|---|---|---|
| **Start Dev Stack** | `make dev` | `./scripts/dev.sh` (runs OPA on :8181 + FastAPI on :8000) |
| **Run All Tests** | `make test` | `uv run pytest` (reads `.env` database configuration) |
| **Run Security Tests** | `make test-sec` | `uv run pytest apps/api/tests/security/` |
| **Run OPA Tests** | `make opa-test` | `opa test packages/policies -v` |
| **Full Quality Gate** | `make gate` | Runs `lint` $\to$ `typecheck` $\to$ `test-all` |
| **Format Code** | `make fmt` | `uv run ruff check --fix . && uv run black .` |
| **Type Check** | `make typecheck` | `uv run mypy` (strict mode across all source files) |
| **Run DB Migration** | `make migrate` | `uv run --package okapi-api alembic upgrade head` |
| **Seed Database** | `make seed` | `uv run --package okapi-api python scripts/seed.py` |

---

## 2. Application & Development Servers

### A. Full Local Development Stack (Recommended)
Starts both the **OPA policy engine (:8181)** in the background and the **FastAPI application (:8000)** with hot-reload enabled. Automatically downloads standalone OPA if not found on system PATH.
```bash
make dev
# or:
./scripts/dev.sh
```
* **Swagger API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc API Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Health Check:** `curl http://localhost:8000/health`

### B. Running FastAPI Server Standalone
Runs only the FastAPI API server with uvicorn:
```bash
make run
# or:
uv run --package okapi-api uvicorn okapi_api.main:app --reload --port 8000
```

### C. Running OPA Policy Engine Standalone
Starts the Open Policy Agent server serving policy evaluation queries at `/v1/data/okapi/authz/result`:
```bash
make opa-serve
# or:
opa run --server --addr localhost:8181 packages/policies
```

### D. Full Containerized Stack (Docker Compose)
Spawns PostgreSQL 16 + pgvector, OPA sidecar, and FastAPI in isolated container networks:
```bash
# Start all containers in background with build
make compose-up
# or:
docker compose -f infra/docker-compose.yml up --build

# Stop and tear down containers and volumes
make compose-down
# or:
docker compose -f infra/docker-compose.yml down -v
```

---

## 3. Database Management & Alembic Migrations

### A. Apply Migrations to PostgreSQL
Upgrades database schema to the latest Alembic revision:
```bash
make migrate
# or:
uv run --package okapi-api alembic -c apps/api/alembic.ini upgrade head
```

### B. Generate a New Migration
Autogenerates a migration script after modifying SQLAlchemy models in `apps/api/src/okapi_api/models/`:
```bash
make revision m="your_migration_description"
# or:
uv run --package okapi-api alembic -c apps/api/alembic.ini revision --autogenerate -m "your_migration_description"
```

### C. Seed Initial Demo Records
Inserts synthetic clinicians, researchers, compliance officers, AI agents, and EHR patient records:
```bash
make seed
# or:
uv run --package okapi-api python scripts/seed.py
```

---

## 4. Automated Testing & Verification Gates

### A. Run Full Pytest Suite (81 Tests)
Runs all unit, integration, and security tests. Automatically inherits database credentials from `.env`:
```bash
make test
# or with an explicit test database URL alias:
OKAPI_TEST_DATABASE_URL="postgresql+psycopg://okapi_user:okapi_password@localhost:5432/okapi" uv run pytest
```

### B. Targeted Subsystem Tests
```bash
# 1. Adversarial Security Tests (Gate bypass, token tampering, DB tampering, cross-tenant RAG)
make test-sec
# or: uv run pytest apps/api/tests/security/

# 2. Integration Tests (PostgreSQL, pgvector embeddings, form workflows)
make test-int
# or: uv run pytest apps/api/tests/integration/

# 3. Unit Tests (Pure business logic, cryptographic HMAC signing, rate limiter)
make test-unit
# or: uv run pytest apps/api/tests/unit/

# 4. Open Policy Agent Rego Unit Tests (HIPAA, DPDP, CDSCO, RBAC/ABAC)
make opa-test
# or: opa test packages/policies -v
```

### C. Run All Tests (Pytest + OPA)
```bash
make test-all
```

---

## 5. Code Quality, Formatting & Static Analysis

```bash
# 1. Complete Quality Gate (Linting + Strict MyPy Typechecking + All Tests)
make gate

# 2. Check for linting violations and import sorting
make lint
# or: uv run ruff check .

# 3. Auto-format codebase using Ruff and Black
make fmt
# or: uv run ruff check --fix . && uv run black .

# 4. Run Strict MyPy Type Checker (63 source files)
make typecheck
# or: uv run mypy
```

---

## 6. Dependency & Workspace Management

```bash
# Sync and install all packages in the uv monorepo according to uv.lock
make sync
# or: uv sync

# Add a runtime dependency to apps/api
uv add <package_name> --package okapi-api

# Add a development dependency to workspace
uv add --dev <package_name>
```
