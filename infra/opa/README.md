# OPA sidecar

The container runs `opa run --server /policies` with `../packages/policies` mounted
read-only at `/policies`. No bundle server or config file is needed at prototype
scale — policies are loaded straight from the mounted directory on startup.

`gate/policy_client.py` calls `POST http://opa:8181/v1/data/okapi/authz/result`
with `{"input": {...}}` and reads `{"result": {...}}`.

To reload policies after editing a `.rego` file, restart the container:
`docker compose -f infra/docker-compose.yml restart opa`.
