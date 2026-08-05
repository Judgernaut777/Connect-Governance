"""Run every revocation-list conformance vector against this implementation.

Same discipline as ``tests/test_grant_vectors.py``: these vectors are a
specification artifact for ADR-052 list sign/verify, so an independent
implementation — e.g. a provider-side verifier in another language, which
consumes lists distributed alongside the trust root — can be judged
conformant without reading this code. They live under
``conformance/grant-vectors/revocation-lists/`` so the grant-vector glob is
undisturbed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from connect_governance.revocations import (
    RevocationList,
    build_revocation_list,
    verify_revocation_list,
)
from connect_governance_kernel import canonical_json

VECTOR_DIR = (
    Path(__file__).resolve().parents[1]
    / "conformance"
    / "grant-vectors"
    / "revocation-lists"
)

REQUIRED_VECTOR_KEYS = {
    "vector_id",
    "description",
    "normative_reference",
    "spec_version",
    "revocation_list_format_version",
    "private_key_pem",
    "public_key_pem",
    "payload",
    "expected_revocation_list",
    "expected_verification",
}


def load_vectors() -> list[dict]:
    files = sorted(VECTOR_DIR.glob("*.json"))
    assert files, f"no revocation-list vectors found in {VECTOR_DIR}"
    return [json.loads(p.read_text(encoding="utf-8")) for p in files]


VECTORS = load_vectors()


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["vector_id"])
def test_revocation_vector_is_well_formed(vector: dict) -> None:
    missing = REQUIRED_VECTOR_KEYS - vector.keys()
    assert not missing, f"{vector.get('vector_id')} missing keys {sorted(missing)}"
    assert vector["description"].strip()
    assert vector["normative_reference"].strip()
    assert "PRIVATE KEY" in vector["private_key_pem"]
    assert "PUBLIC KEY" in vector["public_key_pem"]


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["vector_id"])
def test_signing_matches_vector(vector: dict) -> None:
    """Same fields + same key must reproduce the vector's exact signature."""
    payload = vector["payload"]
    revocation_list = build_revocation_list(
        list_id=payload["list_id"],
        issuer_key_id=payload["issuer_key_id"],
        issued_at=payload["issued_at"],
        revoked_grant_ids=tuple(payload["revoked_grant_ids"]),
        supersedes=payload["supersedes"],
        private_key_pem=vector["private_key_pem"],
    )
    actual = json.loads(canonical_json(revocation_list))
    assert actual == vector["expected_revocation_list"], (
        f"\nvector: {vector['vector_id']} — {vector['description']}"
        f"\nexpected: {json.dumps(vector['expected_revocation_list'], indent=2, sort_keys=True)}"
        f"\nactual:   {json.dumps(actual, indent=2, sort_keys=True)}"
    )


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["vector_id"])
def test_verification_matches_vector(vector: dict) -> None:
    if "tampered_payload" in vector:
        doc = dict(vector["tampered_payload"])
        doc["signature"] = vector["expected_revocation_list"]["signature"]
    else:
        doc = vector["expected_revocation_list"]
    revocation_list = RevocationList.model_validate(doc)
    result = verify_revocation_list(
        revocation_list,
        vector["public_key_pem"],
        expected_key_id=vector["payload"]["issuer_key_id"],
    )
    expected = vector["expected_verification"]
    assert result.valid == expected["valid"], f"{vector['vector_id']}: {result}"
    assert result.signature_valid == expected["signature_valid"]
    assert list(result.failure_codes) == expected["failure_codes"]
    assert result.issuer_key_id == expected["issuer_key_id"]
    assert result.list_id == expected["list_id"]
