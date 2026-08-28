# Okapi

**O**rchestrated **K**nowledge **A**ccess and **P**olicy **I**ntegrity Framework.

Backend-first. Every layer is exercised through the API alone (FastAPI `/docs`, curl,
or a thin test client) before any UI exists. See `architecture_okapi.pdf` for the full
design.

## Monorepo layout

```
apps/
  api/            FastAPI service — Trusted Data Core, Verification Gate, AI Action Layer
packages/
  shared/         okapi-shared — contracts/enums shared across layers (no I/O)
  policies/       OPA/Rego bundle — rbac, abac, one file per compliance regime
infra/            docker-compose (api + OPA sidecar + Postgres/pgvector), Dockerfile
scripts/          bootstrap / migrate / fmt / seed helpers
```

`apps/` holds deployables; `packages/` holds shared libraries. Dependency direction is
strictly downward (architecture doc section 3).

## Tooling

- **[uv](https://docs.astral.sh/uv/) workspace** — one lockfile (`uv.lock`), a
  `pyproject.toml` per member, root `pyproject.toml` for workspace + shared
  ruff/black/mypy/pytest config. (`requirements.txt` is retired.)
- **Python 3.12** (`.python-version`; `uv` fetches it automatically).
- ruff + black + `mypy --strict`, enforced in `.pre-commit-config.yaml` and CI
  (`.github/workflows/ci.yml`).

## Quickstart

```bash
# install uv once: https://docs.astral.sh/uv/getting-started/installation/
uv sync                                                   # create .venv, install all members
cp .env.example .env

uv run --package okapi-api uvicorn okapi_api.main:app --reload   # http://localhost:8000/docs
uv run pytest                                             # workspace test suite
uv run mypy && uv run ruff check .                        # types + lint

docker compose -f infra/docker-compose.yml up --build     # full stack: api + OPA + Postgres
opa test packages/policies -v                             # policy unit tests
```

A `Makefile` wraps the common tasks (`make sync`, `make run`, `make check`,
`make compose-up`). If `uv` is not on `PATH` but was pip-installed, use
`make run UV="python -m uv"`.
