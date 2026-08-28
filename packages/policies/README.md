# okapi-policies

The OPA policy bundle. No Python — this directory is mounted read-only into the OPA
sidecar (`infra/docker-compose.yml`) and evaluated by `gate/policy_client.py` over
HTTP (architecture doc sections 6 and 6.1).

## Files

| File | Package | Purpose |
|------|---------|---------|
| `authz.rego` | `okapi.authz` | Aggregate decision surface. `PolicyClient` reads `data.okapi.authz.result`. |
| `rbac.rego` | `okapi.rbac` | Structural role-based access control. |
| `abac.rego` | `okapi.abac` | Attribute-based rules keyed off JWT `attributes` (department, clearance_level, employment_type). |
| `compliance/hipaa.rego` | `okapi.compliance.hipaa` | HIPAA regime. |
| `compliance/dpdp.rego` | `okapi.compliance.dpdp` | India DPDP regime. |
| `compliance/cdsco.rego` | `okapi.compliance.cdsco` | CDSCO regime. |

One file per compliance regime keeps them pluggable and centrally updatable without
re-engineering application logic (architecture doc section 6.1).

## Test

```
opa test packages/policies -v
opa fmt --list packages/policies      # formatting check
```
