"""Grant signing and verification: determinism, tamper evidence, time windows.

The claims under test are the ones R4 exists for: identical payload and key
produce an identical signature (issuance is reproducible); any mutation of any
signed field fails verification (tamper evidence); and validity is judged
against a caller-supplied instant, never a clock.
"""

from __future__ import annotations

import pytest

from connect_governance_grants import (
    GRANT_FORMAT_VERSION,
    ExecutionGrant,
    GrantPayload,
    public_key_id,
    sign_grant,
    verify_grant,
)
from connect_governance_kernel import canonical_json

T = "2026-08-03T12:00:00Z"

# A fixed test keypair. Private key material in a test fixture is deliberate:
# it is what makes the grant conformance vectors reproducible everywhere.
PRIVATE_KEY_PEM = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MC4CAQAwBQYDK2VwBCIEIDkN5Il+uD9CLnuM+KTlqM+bKDnJql49TksMqQZ8Z3Kh\n"
    "-----END PRIVATE KEY-----\n"
)
PUBLIC_KEY_PEM = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MCowBQYDK2VwAyEA/XluIVKX4rL4Za5ar1AYWE26XHAjLGGYAoycsyl+/m0=\n"
    "-----END PUBLIC KEY-----\n"
)
KEY_ID = "ed25519:f294dcbe2bea2831af6df47eaf039ec5b7b223644dd1689f63be2d90bb5d800a"


def _payload(**kw) -> GrantPayload:
    base = dict(
        grant_format_version=GRANT_FORMAT_VERSION,
        grant_id="g-1",
        decision_record_id="dr-1",
        work_request_id="wr-1",
        work_request_revision="rev-1",
        requesting_principal_id="agent-1",
        organization_id="org-1",
        workspace_id="ws-1",
        provider_id="toolconnect",
        permitted_operations=("tool.invoke",),
        argument_constraints={"tool": "fs.write", "path": "/srv/out"},
        data_classifications=("internal",),
        budget_limit_usd=100.0,
        delegation_depth=0,
        delegation_max_depth=1,
        policy_versions=("pol-1@3",),
        kernel_version="0.0.1",
        not_before="2026-08-03T00:00:00Z",
        not_after="2026-08-04T00:00:00Z",
        issued_at=T,
        issuer_key_id=KEY_ID,
        correlation_id="corr-1",
    )
    base.update(kw)
    return GrantPayload(**base)


def test_key_id_is_sha256_of_raw_public_key() -> None:
    assert public_key_id(PUBLIC_KEY_PEM) == KEY_ID


def test_signing_is_deterministic() -> None:
    """Same payload + same key → byte-identical grant, every time.

    This is what makes issuance reproducible and grant vectors possible.
    """
    first = sign_grant(_payload(), PRIVATE_KEY_PEM)
    for _ in range(25):
        again = sign_grant(_payload(), PRIVATE_KEY_PEM)
        assert canonical_json(again) == canonical_json(first)


def test_signature_is_ed25519_sized_and_scheme_labelled() -> None:
    grant = sign_grant(_payload(), PRIVATE_KEY_PEM)
    import base64

    raw = base64.urlsafe_b64decode(grant.signature + "=" * (-len(grant.signature) % 4))
    assert len(raw) == 64
    assert grant.signature_scheme == "Ed25519"


def test_valid_grant_verifies() -> None:
    grant = sign_grant(_payload(), PRIVATE_KEY_PEM)
    result = verify_grant(grant, PUBLIC_KEY_PEM, at=T)
    assert result.valid
    assert result.signature_valid
    assert result.within_validity_window
    assert result.failure_codes == ()
    assert result.issuer_key_id == KEY_ID


@pytest.mark.parametrize(
    "field, value",
    [
        ("grant_id", "g-2"),
        ("work_request_id", "wr-2"),
        ("work_request_revision", "rev-2"),
        ("requesting_principal_id", "agent-2"),
        ("organization_id", "org-2"),
        ("workspace_id", "ws-2"),
        ("provider_id", "other-provider"),
        ("permitted_operations", ("tool.invoke", "tool.delete")),
        ("budget_limit_usd", 100.01),
        ("delegation_max_depth", 99),
        ("not_after", "2027-01-01T00:00:00Z"),
        ("issued_at", "2026-08-03T12:00:01Z"),
    ],
)
def test_mutating_any_signed_field_fails_verification(field: str, value) -> None:
    """Tamper evidence: a grant is only as good as "change nothing, or it breaks"."""
    grant = sign_grant(_payload(), PRIVATE_KEY_PEM)
    tampered = ExecutionGrant(
        payload=_payload(**{field: value}),
        signature_scheme=grant.signature_scheme,
        signature=grant.signature,
    )
    result = verify_grant(tampered, PUBLIC_KEY_PEM, at=T)
    assert not result.valid
    assert not result.signature_valid
    assert "signature_mismatch" in result.failure_codes


def test_mutating_argument_constraints_fails_verification() -> None:
    """Argument binding is part of the signed payload (RA v0.2 §7, ADR-038)."""
    grant = sign_grant(_payload(), PRIVATE_KEY_PEM)
    tampered = ExecutionGrant(
        payload=_payload(argument_constraints={"tool": "fs.write", "path": "/etc/passwd"}),
        signature_scheme=grant.signature_scheme,
        signature=grant.signature,
    )
    assert not verify_grant(tampered, PUBLIC_KEY_PEM, at=T).valid


def test_wrong_verification_key_fails() -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    other_pub = (
        Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    grant = sign_grant(_payload(), PRIVATE_KEY_PEM)
    assert not verify_grant(grant, other_pub, at=T).valid


def test_expected_key_id_mismatch_is_reported() -> None:
    grant = sign_grant(_payload(), PRIVATE_KEY_PEM)
    result = verify_grant(
        grant, PUBLIC_KEY_PEM, at=T, expected_key_id="ed25519:" + "0" * 64
    )
    assert not result.valid
    assert "key_id_mismatch" in result.failure_codes


def test_validity_window_is_half_open_and_caller_timed() -> None:
    """Before not_before is invalid; at not_before valid; at not_after expired.

    The verifier reads no clock: the same grant is valid or not purely as a
    function of the instant the caller supplies.
    """
    grant = sign_grant(_payload(), PRIVATE_KEY_PEM)
    early = verify_grant(grant, PUBLIC_KEY_PEM, at="2026-08-02T23:59:59Z")
    assert not early.valid and "not_yet_valid" in early.failure_codes

    assert verify_grant(grant, PUBLIC_KEY_PEM, at="2026-08-03T00:00:00Z").valid

    late = verify_grant(grant, PUBLIC_KEY_PEM, at="2026-08-04T00:00:00Z")
    assert not late.valid and "expired" in late.failure_codes


def test_open_validity_bounds_are_open() -> None:
    grant = sign_grant(
        _payload(not_before=None, not_after=None), PRIVATE_KEY_PEM
    )
    assert verify_grant(grant, PUBLIC_KEY_PEM, at="2030-01-01T00:00:00Z").valid


def test_malformed_signature_is_a_result_not_an_exception() -> None:
    """A provider at the point of effect must get an explainable denial."""
    grant = sign_grant(_payload(), PRIVATE_KEY_PEM)
    broken = ExecutionGrant(
        payload=grant.payload,
        signature_scheme=grant.signature_scheme,
        signature="not-base64!!!",
    )
    result = verify_grant(broken, PUBLIC_KEY_PEM, at=T)
    assert not result.valid
    assert "signature_mismatch" in result.failure_codes


def test_signer_refuses_misattributed_issuer() -> None:
    with pytest.raises(ValueError, match="misattribute"):
        sign_grant(_payload(issuer_key_id="ed25519:" + "0" * 64), PRIVATE_KEY_PEM)


def test_grant_round_trips_through_its_canonical_form() -> None:
    """A provider that only ever saw JSON must be able to verify it."""
    import json

    grant = sign_grant(_payload(), PRIVATE_KEY_PEM)
    rehydrated = ExecutionGrant.model_validate(json.loads(canonical_json(grant)))
    assert canonical_json(rehydrated) == canonical_json(grant)
    assert verify_grant(rehydrated, PUBLIC_KEY_PEM, at=T).valid
