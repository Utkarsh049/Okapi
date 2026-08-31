import hashlib
import hmac

from okapi_shared.constants import HASH_ALGORITHM


def hash_value(value: str) -> str:
    """Content hash stored on every ``field_versions`` row."""
    return hashlib.new(HASH_ALGORITHM, value.encode("utf-8")).hexdigest()


def hash_edge(parent_version_id: str, parent_value_hash: str, child_value_hash: str) -> str:
    """Edge hash: ``SHA256(parent_id + parent.value_hash + child.value_hash)`` (arch doc 4.2)."""
    payload = f"{parent_version_id}{parent_value_hash}{child_value_hash}"
    return hashlib.new(HASH_ALGORITHM, payload.encode("utf-8")).hexdigest()


def compute_merkle_root(edge_hashes: list[str]) -> str:
    """Compute deterministic Merkle root accumulator by folding sorted edge hashes."""
    if not edge_hashes:
        return hashlib.new(HASH_ALGORITHM, b"").hexdigest()
    acc = ""
    for h in sorted(edge_hashes):
        acc = hashlib.new(HASH_ALGORITHM, f"{acc}{h}".encode()).hexdigest()
    return acc


def sign_merkle_root(merkle_root: str, secret_key: str) -> str:
    """Generate an HMAC-SHA256 cryptographic signature for a document Merkle root."""
    return hmac.new(
        key=secret_key.encode("utf-8"),
        msg=merkle_root.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def verify_merkle_signature(merkle_root: str, signature: str, secret_key: str) -> bool:
    """Constant-time verification of a document Merkle root signature."""
    expected = sign_merkle_root(merkle_root, secret_key)
    return hmac.compare_digest(expected, signature)
