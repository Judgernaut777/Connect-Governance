"""Run every grant conformance vector against the signing package.

Same discipline as ``tests/test_conformance_vectors.py``: these vectors are a
specification artifact for grant sign/verify (R4), so an independent
implementation — e.g. a provider-side verifier in another language, which R5
needs — can be judged conformant without reading this code.

A vector failing means the implementation or the specification is wrong;
neither is fixed by editing ``expected`` to match observed behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from connect_governance_grants import (
    ExecutionGrant,
    GrantPayload,
    sign_grant,
    verify_grant,
)
from connect_governance_kernel import canonical_json

VECTOR_DIR = Path(__file__).resolve().parents[1] / "conformance" / "grant-vectors"

REQUIRED_VECTOR_KEYS = {
    "vector_id",
    "description",
    "normative_reference",
    "spec_version",
    "grant_format_version",
    "private_key_pem",
    "public_key_pem",
    "payload",
    "verify_at",
    "expected_grant",
    "expected_verification",
}

VECTORS = None


def load_vectors() -> list[dict]:
    files = sorted(VECTOR_DIR.glob("*.json"))
    assert files, f"no grant vectors found in {VECTOR_DIR}"
    return [json.loads(p.read_text(encoding="utf-8")) for p in files]


VECTORS = load_vectors()


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["vector_id"])
def test_grant_vector_is_well_formed(vector: dict) -> None:
    missing = REQUIRED_VECTOR_KEYS - vector.keys()
    assert not missing, f"{vector.get('vector_id')} missing keys {sorted(missing)}"
    assert vector["description"].strip()
    assert vector["normative_reference"].strip()
    # The keypair is embedded so the vector is self-contained: a conformant
    # implementation needs nothing but the file.
    assert "PRIVATE KEY" in vector["private_key_pem"]
    assert "PUBLIC KEY" in vector["public_key_pem"]


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["vector_id"])
def test_signing_matches_vector(vector: dict) -> None:
    """Same payload + same key must reproduce the vector's exact signature."""
    payload = GrantPayload.model_validate(vector["payload"])
    grant = sign_grant(payload, vector["private_key_pem"])
    actual = json.loads(canonical_json(grant))
    assert actual == vector["expected_grant"], (
        f"\nvector: {vector['vector_id']} — {vector['description']}"
        f"\nexpected: {json.dumps(vector['expected_grant'], indent=2, sort_keys=True)}"
        f"\nactual:   {json.dumps(actual, indent=2, sort_keys=True)}"
    )


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["vector_id"])
def test_verification_matches_vector(vector: dict) -> None:
    grant = ExecutionGrant.model_validate(vector["expected_grant"])
    if "tampered_payload" in vector:
        # The vector's signature is genuine, but the payload presented for
        # verification was mutated — verification must fail.
        grant = ExecutionGrant(
            payload=GrantPayload.model_validate(vector["tampered_payload"]),
            signature_scheme=grant.signature_scheme,
            signature=grant.signature,
        )
    result = verify_grant(
        grant, vector["public_key_pem"], at=vector["verify_at"]
    )
    actual = json.loads(canonical_json(result))
    expected = vector["expected_verification"]
    assert actual == expected, (
        f"\nvector: {vector['vector_id']} — {vector['description']}"
        f"\nexpected: {json.dumps(expected, indent=2, sort_keys=True)}"
        f"\nactual:   {json.dumps(actual, indent=2, sort_keys=True)}"
    )


def test_grant_vector_ids_match_filenames() -> None:
    for path in sorted(VECTOR_DIR.glob("*.json")):
        vector = json.loads(path.read_text(encoding="utf-8"))
        assert vector["vector_id"] == path.stem
