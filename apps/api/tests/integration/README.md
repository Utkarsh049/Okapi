# Integration tests

Spin up a real Postgres + OPA and exercise HTTP flows end to end:

```
docker compose -f ../../../infra/docker-compose.test.yml up -d
uv run pytest apps/api/tests/integration
docker compose -f ../../../infra/docker-compose.test.yml down -v
```

Target ≥80% coverage on `services/` and `gate/` — the patent-relevant mechanisms
(architecture doc section 10).
