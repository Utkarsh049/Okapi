"""Project-wide constant values with no better home."""

API_V1_PREFIX = "/api/v1"

# Hash-chain / Merkle DAG algorithm (architecture doc section 4.2).
HASH_ALGORITHM = "sha256"

# OPA sidecar decision path: data.<this>. PolicyClient reads okapi/authz/result.
OPA_DECISION_PATH = "okapi/authz/result"
