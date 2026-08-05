"""ADR-052 revocation lists: deterministic sign/verify, tamper evidence,
monotonic chaining.

The claims under test: identical inputs reproduce an identical signed list
(revocability is auditable and vector-able); any mutation of any signed field
fails verification; verification is pure and offline with stable failure
codes; and the store enforces a single monotonic line of descent per issuer.
Stale-or-missing semantics are deliberately *not* tested here — ADR-052
reserves them to the redeemer, which owns the instant and the grant window.
"""

from __future__ import annotations

import pytest

from connect_governance.db.models import RevocationListRecord
from connect_governance.db.session import create_all, make_engine, session_factory
from connect_governance.revocations import (
    RevocationChainRefused,
    RevocationList,
    build_revocation_list,
    latest_revocation_list,
    record_revocation_list,
    verify_revocation_list,
)
from connect_governance_kernel import canonical_json

T = "2026-08-10T12:00:00Z"

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

# A second keypair, for wrong-key and misattribution cases.
OTHER_PRIVATE_KEY_PEM = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MC4CAQAwBQYDK2VwBCIEIObcKvuZa40TzHj1gVoBl5oMfSRBbppBrok+MPJvkQ1f\n"
    "-----END PRIVATE KEY-----\n"
)
OTHER_PUBLIC_KEY_PEM = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MCowBQYDK2VwAyEA9drO9eVaq5i1Qs4DJzKEvrrmFu8hYwvVAy1oNr3ymc0=\n"
    "-----END PUBLIC KEY-----\n"
)


def _build(**kw):
    args = dict(
        list_id="rl-1",
        issuer_key_id=KEY_ID,
        issued_at=T,
        revoked_grant_ids=("g-1", "g-2"),
        supersedes=None,
        private_key_pem=PRIVATE_KEY_PEM,
    )
    args.update(kw)
    return build_revocation_list(**args)


@pytest.fixture()
def session():
    engine = make_engine()
    create_all(engine)
    with session_factory(engine)() as s:
        yield s


def test_signing_is_deterministic() -> None:
    first = _build()
    for _ in range(25):
        assert canonical_json(_build()) == canonical_json(first)


def test_wire_shape_matches_adr_052() -> None:
    doc = RevocationList.model_validate(__import__("json").loads(canonical_json(_build())))
    assert doc.revocation_list_format_version == "1"
    assert doc.signature_scheme == "Ed25519"
    assert set(doc.model_dump()) == {
        "revocation_list_format_version",
        "issuer_key_id",
        "issued_at",
        "revoked_grant_ids",
        "supersedes",
        "list_id",
        "signature_scheme",
        "signature",
    }


def test_valid_list_verifies() -> None:
    result = verify_revocation_list(_build(), PUBLIC_KEY_PEM, expected_key_id=KEY_ID)
    assert result.valid
    assert result.signature_valid
    assert result.failure_codes == ()
    assert result.list_id == "rl-1"


@pytest.mark.parametrize(
    "field, value",
    [
        ("issuer_key_id", "ed25519:" + "0" * 64),
        ("issued_at", "2026-08-10T12:00:01Z"),
        ("revoked_grant_ids", ("g-1", "g-2", "g-3")),
        ("revoked_grant_ids", ("g-2", "g-1")),
        ("supersedes", "rl-0"),
        ("list_id", "rl-2"),
        ("revocation_list_format_version", "2"),
    ],
)
def test_mutating_any_signed_field_fails_verification(field: str, value) -> None:
    original = _build()
    tampered = original.model_copy(update={field: value})
    result = verify_revocation_list(tampered, PUBLIC_KEY_PEM)
    assert not result.valid
    assert "signature_mismatch" in result.failure_codes


def test_verifying_against_the_wrong_key_fails() -> None:
    result = verify_revocation_list(_build(), OTHER_PUBLIC_KEY_PEM)
    assert not result.valid
    assert "signature_mismatch" in result.failure_codes


def test_key_id_mismatch_is_reported_separately() -> None:
    result = verify_revocation_list(
        _build(), PUBLIC_KEY_PEM, expected_key_id="ed25519:" + "f" * 64
    )
    assert not result.valid
    assert "key_id_mismatch" in result.failure_codes


def test_unsupported_scheme_is_a_stable_failure_code() -> None:
    doc = dict(_build().model_dump(), signature_scheme="RSA")
    result = verify_revocation_list(doc, PUBLIC_KEY_PEM)
    assert not result.valid
    assert "unsupported_scheme" in result.failure_codes
    assert "signature_mismatch" in result.failure_codes


def test_unsupported_format_version_is_refused() -> None:
    doc = dict(_build().model_dump(), revocation_list_format_version="99")
    result = verify_revocation_list(doc, PUBLIC_KEY_PEM)
    assert not result.valid
    assert "unsupported_format_version" in result.failure_codes


def test_signing_key_must_match_claimed_issuer() -> None:
    with pytest.raises(ValueError, match="misattribute"):
        _build(private_key_pem=OTHER_PRIVATE_KEY_PEM)


def test_round_trip_from_canonical_json() -> None:
    original = _build()
    restored = RevocationList.model_validate(
        __import__("json").loads(canonical_json(original))
    )
    assert verify_revocation_list(restored, PUBLIC_KEY_PEM).valid


def test_first_list_must_not_supersede(session) -> None:
    with pytest.raises(RevocationChainRefused):
        record_revocation_list(session, _build(supersedes="rl-ghost"))


def test_chain_advances_monotonically(session) -> None:
    record_revocation_list(session, _build())
    second = _build(
        list_id="rl-2",
        supersedes="rl-1",
        issued_at="2026-08-10T13:00:00Z",
        revoked_grant_ids=("g-1", "g-2", "g-9"),
    )
    record_revocation_list(session, second)

    head = latest_revocation_list(session, KEY_ID)
    assert head is not None and head.list_id == "rl-2"
    assert head.supersedes == "rl-1"


def test_fork_or_gap_in_chain_is_refused(session) -> None:
    record_revocation_list(session, _build())
    with pytest.raises(RevocationChainRefused):
        # Skips the head: claims a parent that is not rl-1.
        record_revocation_list(session, _build(list_id="rl-2", supersedes="rl-0"))
    with pytest.raises(RevocationChainRefused):
        # A second root: chain already exists for this issuer.
        record_revocation_list(session, _build(list_id="rl-2", supersedes=None))


def test_recorded_artifact_round_trips_byte_identically(session) -> None:
    built = _build()
    record_revocation_list(session, built)
    row = session.get(RevocationListRecord, "rl-1")
    assert row is not None
    assert row.list_json == canonical_json(built)
    assert row.issuer_key_id == KEY_ID
    assert row.supersedes is None
