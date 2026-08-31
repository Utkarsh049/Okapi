# Okapi monorepo tasks. Requires `uv` on PATH (https://docs.astral.sh/uv/).
# On a machine where uv was installed via `pip install --user uv`, run `UV="python -m uv" make <target>`.

UV ?= uv
COMPOSE ?= docker compose -f infra/docker-compose.yml

OPA ?= $(shell command -v opa 2>/dev/null || ([ -f .tools/opa ] && echo .tools/opa) || echo .tools/opa.exe)

# Automatically read database URL from .env if present, otherwise default to standard local test DB
export OKAPI_TEST_DATABASE_URL ?= $(shell grep OKAPI_DATABASE_URL .env 2>/dev/null | cut -d '=' -f2- | tr -d '"' || echo "postgresql+psycopg://okapi_user:okapi_password@localhost:5432/okapi")

.PHONY: dev sync run test test-unit test-int test-sec test-all lint fmt typecheck check gate migrate revision seed demo opa-serve opa-test compose-up compose-down

dev:
	./scripts/dev.sh

sync:
	$(UV) sync

run:
	$(UV) run --package okapi-api uvicorn okapi_api.main:app --reload

test:
	$(UV) run pytest

test-unit:
	$(UV) run pytest apps/api/tests/unit/

test-int:
	$(UV) run pytest apps/api/tests/integration/

test-sec:
	$(UV) run pytest apps/api/tests/security/

test-all: test opa-test

lint:
	$(UV) run ruff check .

fmt:
	$(UV) run ruff check --fix .
	$(UV) run black .

typecheck:
	$(UV) run mypy

check: lint typecheck test

gate: lint typecheck test-all

migrate:
	$(UV) run --package okapi-api alembic -c apps/api/alembic.ini upgrade head

revision:
	$(UV) run --package okapi-api alembic -c apps/api/alembic.ini revision --autogenerate -m "$(m)"

seed:
	$(UV) run --package okapi-api python scripts/seed.py

demo:
	$(UV) run --package okapi-api python scripts/demo.py

opa-serve:
	$(OPA) run --server --addr localhost:8181 packages/policies

compose-up:
	$(COMPOSE) up --build

compose-down:
	$(COMPOSE) down -v

opa-test:
	$(OPA) test packages/policies -v
