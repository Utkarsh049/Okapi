# Okapi monorepo tasks. Requires `uv` on PATH (https://docs.astral.sh/uv/).
# On a machine where uv was installed via `pip install --user uv`, run `UV="python -m uv" make <target>`.

UV ?= uv
COMPOSE ?= docker compose -f infra/docker-compose.yml

.PHONY: sync run test lint fmt typecheck check migrate revision compose-up compose-down opa-test

sync:
	$(UV) sync

run:
	$(UV) run --package okapi-api uvicorn okapi_api.main:app --reload

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check .

fmt:
	$(UV) run ruff check --fix .
	$(UV) run black .

typecheck:
	$(UV) run mypy

check: lint typecheck test

migrate:
	$(UV) run --package okapi-api alembic -c apps/api/alembic.ini upgrade head

revision:
	$(UV) run --package okapi-api alembic -c apps/api/alembic.ini revision --autogenerate -m "$(m)"

compose-up:
	$(COMPOSE) up --build

compose-down:
	$(COMPOSE) down -v

opa-test:
	opa test packages/policies -v
