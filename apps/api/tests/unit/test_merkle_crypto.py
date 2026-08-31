"""Unit tests for Merkle root computation and HMAC cryptographic signing."""

from okapi_api.core.hashing import (
    compute_merkle_root,
    sign_merkle_root,
    verify_merkle_signature,
)

SECRET = "super-secret-okapi-signing-key-for-test-32b"


def test_compute_merkle_root_empty() -> None:
    root = compute_merkle_root([])
    assert len(root) == 64
    assert isinstance(root, str)


def test_compute_merkle_root_order_invariant() -> None:
    hashes_a = ["hash_3", "hash_1", "hash_2"]
    hashes_b = ["hash_1", "hash_2", "hash_3"]
    assert compute_merkle_root(hashes_a) == compute_merkle_root(hashes_b)


def test_sign_and_verify_merkle_signature_valid() -> None:
    root = compute_merkle_root(["e1", "e2", "e3"])
    sig = sign_merkle_root(root, SECRET)
    assert verify_merkle_signature(root, sig, SECRET) is True


def test_verify_merkle_signature_tampered_root_fails() -> None:
    root1 = compute_merkle_root(["e1", "e2"])
    root2 = compute_merkle_root(["e1", "e2_tampered"])
    sig1 = sign_merkle_root(root1, SECRET)
    assert verify_merkle_signature(root2, sig1, SECRET) is False


def test_verify_merkle_signature_invalid_secret_fails() -> None:
    root = compute_merkle_root(["e1", "e2"])
    sig = sign_merkle_root(root, SECRET)
    assert verify_merkle_signature(root, sig, "wrong-key") is False
